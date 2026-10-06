"""Integration tests. Run only when Neo4j is reachable (inside docker compose)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.graph import client as neo
from app.main import app

pytestmark = pytest.mark.skipif(not neo.ping(), reason="neo4j not reachable")


@pytest.fixture(scope="module")
def api():
    return TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def seeded():
    from app.seed import run_seed
    run_seed()


def test_health(api):
    body = api.get("/health").json()
    assert body["status"] == "ok" and body["neo4j"] == "ok"


def test_seed_is_idempotent():
    from app.seed import counts, run_seed
    before = counts()
    run_seed()
    assert counts() == before


def test_object_graph_is_not_whole_graph(api):
    body = api.get("/api/objects/bo:customer/graph", params={"depth": 1}).json()
    ids = {n["id"] for n in body["nodes"]}
    assert "bo:customer" in ids
    assert "table:billing.invoice" not in ids


def test_impact_contains_required_fields(api):
    body = api.get("/api/impact", params={"object_id": "table:customer.customer", "change_type": "schema_change"}).json()
    for key in ("affected", "owners", "warnings", "unknownCount"):
        assert key in body
    assert all("path" in a for a in body["affected"])


def test_unknown_inbox(api):
    body = api.get("/api/unknowns").json()
    assert any(u["id"] == "unknown:UNKNOWN-001" for u in body) or api.get("/api/unknowns", params={"status": "all"}).json()
