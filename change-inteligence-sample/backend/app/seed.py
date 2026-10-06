"""Idempotent seed: loads ontology + fixtures into Neo4j.

Nodes are MERGEd by `id`, relations by (type, id), evidence by `id`. Running it twice leaves
the node/relation counts unchanged. Resolved Unknown state is preserved: a relation that was moved
by a Resolve (and therefore carries `resolved_from`) is not re-created on the Unknown.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from app.config import settings
from app.graph import client
from app.services.ontology import load_ontology

log = logging.getLogger("seed")

_IDENT = re.compile(r"^[A-Z_]+$")


def _load_yaml(path: Path, key: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get(key, [])


def load_fixtures(fixtures_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    base = fixtures_dir or settings.fixtures_dir
    return {
        "objects": _load_yaml(base / "objects.yaml", "objects"),
        "relations": _load_yaml(base / "relations.yaml", "relations"),
        "evidence": _load_yaml(base / "evidence.yaml", "evidence"),
    }


def validate_fixtures(fixtures: dict[str, list[dict[str, Any]]], ontology: dict[str, Any]) -> list[str]:
    """Return a list of validation errors (empty when the fixtures are consistent with the ontology)."""
    errors: list[str] = []
    object_types = {t["type"] for t in ontology["object_types"]}
    relation_types = {t["type"]: t for t in ontology["relation_types"]}
    ids: dict[str, str] = {}
    for obj in fixtures["objects"]:
        if obj["type"] not in object_types:
            errors.append(f"object {obj['id']}: unknown type {obj['type']}")
        if obj["id"] in ids:
            errors.append(f"object {obj['id']}: duplicate id")
        ids[obj["id"]] = obj["type"]
    rel_ids: set[str] = set()
    for rel in fixtures["relations"]:
        rid = rel.get("id")
        if not rid:
            errors.append(f"relation {rel}: missing id")
            continue
        if rid in rel_ids:
            errors.append(f"relation {rid}: duplicate id")
        rel_ids.add(rid)
        spec = relation_types.get(rel["type"])
        if spec is None or not _IDENT.match(rel["type"]):
            errors.append(f"relation {rid}: unknown type {rel['type']}")
            continue
        for end in ("from", "to"):
            if rel[end] not in ids:
                errors.append(f"relation {rid}: {end} object {rel[end]} does not exist")
        allowed_from, allowed_to = spec.get("from", ["*"]), spec.get("to", ["*"])
        if rel["from"] in ids and "*" not in allowed_from and ids[rel["from"]] not in allowed_from:
            errors.append(f"relation {rid}: from type {ids[rel['from']]} not allowed for {rel['type']}")
        if rel["to"] in ids and "*" not in allowed_to and ids[rel["to"]] not in allowed_to:
            errors.append(f"relation {rid}: to type {ids[rel['to']]} not allowed for {rel['type']}")
    ev_ids: set[str] = set()
    for ev in fixtures["evidence"]:
        if ev["id"] in ev_ids:
            errors.append(f"evidence {ev['id']}: duplicate id")
        ev_ids.add(ev["id"])
        if ev.get("relation_id") not in rel_ids:
            errors.append(f"evidence {ev['id']}: relation {ev.get('relation_id')} does not exist")
    return errors


def ensure_constraints() -> None:
    client.run("CREATE CONSTRAINT object_id IF NOT EXISTS FOR (n:Object) REQUIRE n.id IS UNIQUE")
    client.run("CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (e:Evidence) REQUIRE e.id IS UNIQUE")
    client.run("CREATE INDEX evidence_relation IF NOT EXISTS FOR (e:Evidence) ON (e.relation_id)")


def _node_props(obj: dict[str, Any]) -> dict[str, Any]:
    props = {k: v for k, v in obj.items() if k not in ("type",)}
    if "name" not in props:
        props["name"] = obj["id"]
    return props


def seed_objects(objects: list[dict[str, Any]]) -> None:
    statements = []
    for obj in objects:
        label = obj["type"]
        if not _IDENT.match(label.upper()) or not label.isidentifier():
            raise ValueError(f"invalid label {label}")
        props = _node_props(obj)
        # Unknown.status is only set on create so a resolved Unknown stays resolved after re-seed.
        if label == "Unknown":
            status = props.pop("status", "open")
            query = (
                f"MERGE (n:Object:{label} {{id: $id}}) "
                "ON CREATE SET n.status = $status "
                "SET n += $props"
            )
            statements.append((query, {"id": obj["id"], "status": status, "props": props}))
        else:
            query = f"MERGE (n:Object:{label} {{id: $id}}) SET n += $props"
            statements.append((query, {"id": obj["id"], "props": props}))
    client.run_many(statements)


def seed_relations(relations: list[dict[str, Any]]) -> None:
    statements = []
    for rel in relations:
        rtype = rel["type"]
        if not _IDENT.match(rtype):
            raise ValueError(f"invalid relation type {rtype}")
        props = {k: v for k, v in rel.items() if k not in ("type", "from", "to")}
        # Skip relations that a Resolve already moved away from this source (audit trail kept on the moved rel).
        query = (
            "MATCH (a:Object {id: $from}), (b:Object {id: $to}) "
            "OPTIONAL MATCH ()-[moved {id: $rid}]->() WHERE moved.resolved_from = $from "
            "WITH a, b, moved WHERE moved IS NULL "
            f"MERGE (a)-[r:{rtype} {{id: $rid}}]->(b) SET r += $props"
        )
        statements.append((query, {"from": rel["from"], "to": rel["to"], "rid": rel["id"], "props": props}))
    client.run_many(statements)


def seed_evidence(evidence: list[dict[str, Any]]) -> None:
    statements = []
    for ev in evidence:
        props = dict(ev)
        if isinstance(props.get("confidence"), (int, float)):
            props["confidence"] = float(props["confidence"])
        statements.append(("MERGE (e:Evidence {id: $id}) SET e += $props", {"id": ev["id"], "props": props}))
    client.run_many(statements)


def counts() -> dict[str, int]:
    nodes = client.run("MATCH (n:Object) RETURN count(n) AS c")[0]["c"]
    rels = client.run("MATCH (:Object)-[r]->(:Object) RETURN count(r) AS c")[0]["c"]
    ev = client.run("MATCH (e:Evidence) RETURN count(e) AS c")[0]["c"]
    return {"nodes": nodes, "relations": rels, "evidence": ev}


def reset_graph() -> None:
    """Delete every node and relation (demo reset). Constraints are kept."""
    client.run("MATCH (n) DETACH DELETE n")
    log.warning("graph reset: all nodes and relations deleted")


def run_seed(fixtures_dir: Path | None = None, reset: bool = False) -> dict[str, int]:
    ontology = load_ontology()
    fixtures = load_fixtures(fixtures_dir)
    errors = validate_fixtures(fixtures, ontology)
    if errors:
        for e in errors:
            log.error("fixture validation: %s", e)
        raise SystemExit(f"{len(errors)} fixture validation error(s)")
    before = counts() if _graph_ready() else {"nodes": 0, "relations": 0, "evidence": 0}
    if reset:
        reset_graph()
    ensure_constraints()
    seed_objects(fixtures["objects"])
    seed_relations(fixtures["relations"])
    seed_evidence(fixtures["evidence"])
    after = counts()
    log.info("seed complete: before=%s after=%s", before, after)
    return after


def _graph_ready() -> bool:
    return client.ping()


def main() -> int:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    import time

    for attempt in range(30):
        if client.ping():
            break
        log.info("waiting for neo4j at %s (attempt %d)", settings.neo4j_uri, attempt + 1)
        time.sleep(2)
    else:
        log.error("neo4j not reachable")
        return 1
    reset = os.environ.get("SEED_RESET", "").lower() in ("1", "true", "yes")
    result = run_seed(reset=reset)
    print(f"SEED OK nodes={result['nodes']} relations={result['relations']} evidence={result['evidence']}")
    client.close_driver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
