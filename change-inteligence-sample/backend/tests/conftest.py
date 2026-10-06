from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.graph.snapshot import Edge, Evidence, GraphSnapshot, Node
from app.seed import load_fixtures
from app.services.ontology import load_ontology

ROOT = Path(__file__).resolve().parents[2]


def _dir(env: str, fallback: str) -> Path:
    p = Path(os.environ.get(env) or "")
    if p and p.exists():
        return p
    return ROOT / fallback


@pytest.fixture(scope="session")
def fixtures():
    return load_fixtures(_dir("FIXTURES_DIR", "fixtures"))


@pytest.fixture(scope="session")
def ontology():
    return load_ontology(str(_dir("ONTOLOGY_DIR", "ontology")))


@pytest.fixture(scope="session")
def rules(ontology):
    return ontology["rules"]


def snapshot_from_fixtures(fx) -> GraphSnapshot:
    snap = GraphSnapshot()
    for obj in fx["objects"]:
        props = {k: v for k, v in obj.items() if k != "type"}
        props.setdefault("name", obj["id"])
        snap.add_node(Node(id=obj["id"], type=obj["type"], props=props))
    for rel in fx["relations"]:
        props = {k: v for k, v in rel.items() if k not in ("type", "from", "to")}
        snap.add_edge(Edge(id=rel["id"], type=rel["type"], source=rel["from"], target=rel["to"], props=props))
    for ev in fx["evidence"]:
        snap.add_evidence(Evidence(id=ev["id"], relation_id=ev["relation_id"], props=dict(ev)))
    return snap


@pytest.fixture(scope="session")
def snap(fixtures) -> GraphSnapshot:
    return snapshot_from_fixtures(fixtures)
