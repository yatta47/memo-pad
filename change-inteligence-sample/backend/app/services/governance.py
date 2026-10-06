"""Governance (US-05): direct DB access, owner missing, unknown counts."""
from __future__ import annotations

from typing import Any

from app.domain.models import DirectAccessOut, GovernanceSummary, ObjectRef
from app.graph.snapshot import GraphSnapshot
from app.services.common import evidence_out, ref

DEFAULT_RULES: dict[str, Any] = {
    "direct_access": {"property": "access_mode", "value": "direct",
                      "severity_by_source_type": {"Service": "HIGH", "Batch": "MEDIUM", "Unknown": "HIGH"}},
    "owner_required_for": ["Service", "Batch", "BusinessObject"],
}


def _canonical_apis(snap: GraphSnapshot, table_id: str) -> list[ObjectRef]:
    """APIs that operate on the Business Object represented by this table (design §9.3)."""
    apis: dict[str, ObjectRef] = {}
    for rep in snap.out_edges(table_id, "REPRESENTS"):
        for op in snap.in_edges(rep.target, "OPERATES_ON"):
            api = snap.nodes.get(op.source)
            if api:
                apis[api.id] = ref(api)
    return list(apis.values())


def direct_access(snap: GraphSnapshot, rules: dict[str, Any] | None = None) -> list[DirectAccessOut]:
    rules = {**DEFAULT_RULES, **(rules or {})}
    da = rules["direct_access"]
    prop, value = da.get("property", "access_mode"), da.get("value", "direct")
    severity_map = da.get("severity_by_source_type", {})
    out: list[DirectAccessOut] = []
    for e in snap.edges:
        if e.type not in ("READS", "WRITES"):
            continue
        src, tgt = snap.nodes.get(e.source), snap.nodes.get(e.target)
        if src is None or tgt is None or tgt.type != "Table":
            continue
        if src.type == "Unknown" and src.props.get("status") == "resolved":
            continue
        is_direct = e.props.get(prop) == value
        if not is_direct:
            # Fallback rule (§9.3): a non-owner accessing a table without any canonical route through its own APIs.
            provides_api_for_bo = any(
                op.source in {p.target for p in snap.out_edges(src.id, "PROVIDES")}
                for rep in snap.out_edges(tgt.id, "REPRESENTS")
                for op in snap.in_edges(rep.target, "OPERATES_ON")
            )
            is_direct = e.props.get(prop) not in ("owner",) and not provides_api_for_bo and src.type != "Unknown"
        if not is_direct:
            continue
        canonical = _canonical_apis(snap, tgt.id)
        called = {c.target for c in snap.out_edges(src.id, "CALLS")}
        bypasses = any(a.id in called for a in canonical)
        out.append(
            DirectAccessOut(
                relationId=e.id, relation=e.type, source=ref(src), sourceOwners=[ref(t) for t in snap.owners_of(src.id)],
                target=ref(tgt), targetOwners=[ref(t) for t in _table_owners(snap, tgt.id)],
                accessMode=str(e.props.get(prop) or "direct"), severity=severity_map.get(src.type, "MEDIUM"),
                bypassesApi=bypasses, canonicalApis=canonical, note=e.props.get("note"),
                evidence=[evidence_out(ev) for ev in snap.evidence_for(e.id)],
            )
        )
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(out, key=lambda d: (order[d.severity], d.target.name, d.source.name))


def _table_owners(snap: GraphSnapshot, table_id: str):
    found = {}
    for e in snap.in_edges(table_id, "WRITES"):
        for t in snap.owners_of(e.source):
            found[t.id] = t
    for e in snap.out_edges(table_id, "REPRESENTS"):
        for t in snap.owners_of(e.target):
            found[t.id] = t
    return list(found.values())


def owner_missing(snap: GraphSnapshot, rules: dict[str, Any] | None = None) -> list[ObjectRef]:
    rules = {**DEFAULT_RULES, **(rules or {})}
    required = set(rules.get("owner_required_for", []))
    return sorted(
        (ref(n) for n in snap.active_nodes() if n.type in required and not snap.owners_of(n.id)),
        key=lambda r: (r.type, r.name),
    )


def summary(snap: GraphSnapshot, rules: dict[str, Any] | None = None) -> GovernanceSummary:
    da = direct_access(snap, rules)
    by_sev: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for d in da:
        by_sev[d.severity] += 1
    unknowns = snap.nodes_of_type("Unknown")
    return GovernanceSummary(
        directAccessCount=len(da), directAccessBySeverity=by_sev, ownerMissing=owner_missing(snap, rules),
        unknownOpen=sum(1 for u in unknowns if u.props.get("status") != "resolved"),
        unknownResolved=sum(1 for u in unknowns if u.props.get("status") == "resolved"),
        objectCount=len(snap.nodes), relationCount=len(snap.edges),
    )
