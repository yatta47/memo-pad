"""Unknown Inbox + Resolve (US-04)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException

from app.domain.models import NewObjectIn, ObjectRef, ResolveIn, ResolveOut, UnknownDetail, UnknownSummary
from app.graph import client
from app.graph.snapshot import GraphSnapshot, Node
from app.services.common import evidence_out, ref, relation_out

_IDENT = re.compile(r"^[A-Z_]+$")


def _summary(snap: GraphSnapshot, node: Node) -> UnknownSummary:
    edges = snap.out_edges(node.id) + snap.in_edges(node.id)
    evidence = [ev for e in edges for ev in snap.evidence_for(e.id)]
    last_seen = max((str(ev.props.get("last_seen")) for ev in evidence if ev.props.get("last_seen")), default=None)
    return UnknownSummary(
        id=node.id, name=node.name, unknown_type=node.props.get("unknown_type"), status=str(node.props.get("status", "open")),
        hint=node.props.get("hint"), relationCount=len(edges), evidenceCount=len(evidence), lastSeen=last_seen,
        resolvedTo=node.props.get("resolved_to"),
    )


def list_unknowns(snap: GraphSnapshot, status: str | None = "open") -> list[UnknownSummary]:
    out = []
    for n in snap.nodes_of_type("Unknown"):
        if status and status != "all" and str(n.props.get("status", "open")) != status:
            continue
        out.append(_summary(snap, n))
    return sorted(out, key=lambda u: (u.status != "open", u.id))


def get_unknown(snap: GraphSnapshot, unknown_id: str) -> UnknownDetail | None:
    node = snap.nodes.get(unknown_id)
    if node is None or node.type != "Unknown":
        return None
    edges = snap.out_edges(unknown_id) + snap.in_edges(unknown_id)
    rels = [relation_out(snap, e, unknown_id) for e in edges]
    evidence = [evidence_out(ev) for e in edges for ev in snap.evidence_for(e.id)]
    # Candidate Known objects ranked by how well their id/name/description match the Unknown's hint + evidence text.
    corpus = " ".join([str(node.props.get("hint", "")), *(str(ev.source_ref or "") for ev in evidence)]).lower()
    corpus_tokens = set(re.split(r"[^a-z0-9]+", corpus)) - {""}

    def _score(n: Node) -> float:
        tokens = set(re.split(r"[^a-z0-9]+", f"{n.id} {n.name} {n.props.get('description', '')} {n.props.get('system', '')}".lower())) - {"", "service", "batch"}
        hits = len(tokens & corpus_tokens)
        # scheduled / nightly access patterns point at a Batch rather than an online Service
        bonus = 0.5 if n.type == "Batch" and any(k in corpus for k in ("nightly", "daily", "batch", "cron", "schedule")) else 0.0
        # an object that already has the same relation to the same target is a weaker candidate (it is already known)
        already = any(e2.target == e.target and e2.type == e.type for e in snap.out_edges(unknown_id) for e2 in snap.out_edges(n.id))
        return hits + bonus - (1.0 if already else 0.0)

    known = snap.nodes_of_type("Service", "Batch")
    candidates = [ref(n) for n in sorted(known, key=lambda n: (-_score(n), n.type != "Batch", n.name))]
    return UnknownDetail(**_summary(snap, node).model_dump(), relations=rels, evidence=evidence, candidates=candidates)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "object"


def _create_known(new_obj: NewObjectIn) -> str:
    label = new_obj.type
    new_id = new_obj.id or f"{label.lower()}:{_slug(new_obj.name)}"
    exists = client.run("MATCH (n:Object {id: $id}) RETURN n.id AS id", id=new_id)
    if exists:
        raise HTTPException(status_code=409, detail=f"object {new_id} already exists")
    props = {"id": new_id, "name": new_obj.name}
    if new_obj.system:
        props["system"] = new_obj.system
    statements = [(f"CREATE (n:Object:{label}) SET n = $props", {"props": props})]
    if new_obj.team_id:
        statements.append((
            "MATCH (t:Team {id: $team}), (n:Object {id: $id}) "
            "MERGE (t)-[r:OWNS {id: $rid}]->(n) SET r.observation_type = 'manual'",
            {"team": new_obj.team_id, "id": new_id, "rid": f"rel:owns-{_slug(new_id)}"},
        ))
    client.run_many(statements)
    return new_id


def resolve(snap: GraphSnapshot, unknown_id: str, body: ResolveIn) -> ResolveOut:
    node = snap.nodes.get(unknown_id)
    if node is None or node.type != "Unknown":
        raise HTTPException(status_code=404, detail="unknown not found")
    if node.props.get("status") == "resolved":
        raise HTTPException(status_code=409, detail="unknown already resolved")
    if bool(body.target_id) == bool(body.new_object):
        raise HTTPException(status_code=422, detail="provide exactly one of target_id or new_object")

    target_id = body.target_id or _create_known(body.new_object)  # type: ignore[arg-type]
    target_rows = client.run("MATCH (n:Object {id: $id}) RETURN n.id AS id, labels(n) AS labels, n.name AS name", id=target_id)
    if not target_rows:
        raise HTTPException(status_code=404, detail=f"target {target_id} not found")
    if target_id == unknown_id or "Unknown" in target_rows[0]["labels"]:
        raise HTTPException(status_code=422, detail="target must be a Known object")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    statements: list[tuple[str, dict]] = []
    moved = 0
    # Re-attach every relation touching the Unknown to the Known object, keeping relation ids so
    # Evidence (joined by relation_id) is inherited. Audit trail: resolved_from on relation + evidence.
    for e in snap.out_edges(unknown_id):
        if not _IDENT.match(e.type):
            continue
        statements.append((
            f"MATCH (u:Object {{id: $uid}})-[old:{e.type} {{id: $rid}}]->(x:Object) "
            f"MATCH (k:Object {{id: $kid}}) "
            f"MERGE (k)-[r:{e.type} {{id: $rid}}]->(x) "
            "SET r += properties(old), r.resolved_from = $uid, r.resolved_at = $now "
            "DELETE old",
            {"uid": unknown_id, "rid": e.id, "kid": target_id, "now": now},
        ))
        moved += 1
    for e in snap.in_edges(unknown_id):
        if not _IDENT.match(e.type):
            continue
        statements.append((
            f"MATCH (x:Object)-[old:{e.type} {{id: $rid}}]->(u:Object {{id: $uid}}) "
            f"MATCH (k:Object {{id: $kid}}) "
            f"MERGE (x)-[r:{e.type} {{id: $rid}}]->(k) "
            "SET r += properties(old), r.resolved_from = $uid, r.resolved_at = $now "
            "DELETE old",
            {"uid": unknown_id, "rid": e.id, "kid": target_id, "now": now},
        ))
        moved += 1
    rel_ids = [e.id for e in snap.out_edges(unknown_id) + snap.in_edges(unknown_id)]
    statements.append((
        "MATCH (ev:Evidence) WHERE ev.relation_id IN $rids SET ev.resolved_from = $uid, ev.resolved_at = $now",
        {"rids": rel_ids, "uid": unknown_id, "now": now},
    ))
    statements.append((
        "MATCH (u:Object:Unknown {id: $uid}) SET u.status = 'resolved', u.resolved_to = $kid, u.resolved_at = $now, u.resolve_note = $note",
        {"uid": unknown_id, "kid": target_id, "now": now, "note": body.note},
    ))
    client.run_many(statements)

    inherited = sum(len(snap.evidence_for(rid)) for rid in rel_ids)
    from app.graph.snapshot import load_snapshot  # fresh state after write

    fresh = load_snapshot()
    t = fresh.nodes[target_id]
    return ResolveOut(unknown=_summary(fresh, fresh.nodes[unknown_id]), resolvedTo=ref(t), movedRelations=moved, inheritedEvidence=inherited)
