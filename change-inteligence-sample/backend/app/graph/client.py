"""Thin wrapper around the Neo4j driver. The frontend never talks to Neo4j; only this module does."""
from __future__ import annotations

import atexit
import logging
from typing import Any

from neo4j import Driver, GraphDatabase

from app.config import settings

log = logging.getLogger(__name__)

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            notifications_min_severity="WARNING",  # hide INFORMATION-level planner hints in logs
        )
        atexit.register(close_driver)
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run(query: str, **params: Any) -> list[dict[str, Any]]:
    """Run a Cypher query in an auto-commit transaction and return records as dicts."""
    with get_driver().session() as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


def run_many(statements: list[tuple[str, dict[str, Any]]]) -> None:
    """Run several statements in a single write transaction."""
    def _work(tx):
        for query, params in statements:
            tx.run(query, **params)

    with get_driver().session() as session:
        session.execute_write(_work)


def ping() -> bool:
    try:
        rows = run("RETURN 1 AS ok")
        return bool(rows and rows[0]["ok"] == 1)
    except Exception as exc:  # pragma: no cover - depends on infra
        log.warning("neo4j ping failed: %s", exc)
        return False
