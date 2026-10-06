"""Loads the Git-managed ontology YAML (object types, relation types, rules)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import settings


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_ontology(ontology_dir: str | None = None) -> dict[str, Any]:
    base = Path(ontology_dir) if ontology_dir else settings.ontology_dir
    return {
        "object_types": _load(base / "object-types.yaml").get("object_types", []),
        "relation_types": _load(base / "relation-types.yaml").get("relation_types", []),
        "rules": _load(base / "rules.yaml"),
    }


def object_type_names() -> set[str]:
    return {t["type"] for t in load_ontology()["object_types"]}


def relation_type_names() -> set[str]:
    return {t["type"] for t in load_ontology()["relation_types"]}


def rules() -> dict[str, Any]:
    return load_ontology()["rules"]
