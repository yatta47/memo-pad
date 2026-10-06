"""In-memory snapshot of the whole Knowledge Graph.

The PoC graph is tiny (tens of nodes), so analysis services (impact, governance, design review)
load a snapshot and traverse in Python. This keeps the algorithms unit-testable without Neo4j.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.graph import client

OBJECT_LABELS = {"Team", "Service", "API", "BusinessObject", "Database", "Table", "Batch", "Unknown"}


@dataclass
class Node:
    id: str
    type: str
    props: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.props.get("name") or self.id)


@dataclass
class Edge:
    id: str
    type: str
    source: str
    target: str
    props: dict[str, Any]


@dataclass
class Evidence:
    id: str
    relation_id: str
    props: dict[str, Any]


@dataclass
class GraphSnapshot:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    _out: dict[str, list[Edge]] = field(default_factory=lambda: defaultdict(list), repr=False)
    _in: dict[str, list[Edge]] = field(default_factory=lambda: defaultdict(list), repr=False)
    _ev: dict[str, list[Evidence]] = field(default_factory=lambda: defaultdict(list), repr=False)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)
        self._out[edge.source].append(edge)
        self._in[edge.target].append(edge)

    def add_evidence(self, ev: Evidence) -> None:
        self.evidence.append(ev)
        self._ev[ev.relation_id].append(ev)

    def out_edges(self, node_id: str, rel: str | None = None) -> list[Edge]:
        return [e for e in self._out.get(node_id, []) if rel is None or e.type == rel]

    def in_edges(self, node_id: str, rel: str | None = None) -> list[Edge]:
        return [e for e in self._in.get(node_id, []) if rel is None or e.type == rel]

    def evidence_for(self, relation_id: str) -> list[Evidence]:
        return self._ev.get(relation_id, [])

    def owners_of(self, node_id: str) -> list[Node]:
        return [self.nodes[e.source] for e in self.in_edges(node_id, "OWNS") if e.source in self.nodes]

    def nodes_of_type(self, *types: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.type in types]

    def active_nodes(self) -> Iterable[Node]:
        """Nodes excluding resolved Unknowns (kept for audit, hidden from analysis)."""
        for n in self.nodes.values():
            if n.type == "Unknown" and n.props.get("status") == "resolved":
                continue
            yield n


def _node_type(labels: list[str]) -> str:
    for label in labels:
        if label in OBJECT_LABELS:
            return label
    return labels[0] if labels else "Object"


def load_snapshot() -> GraphSnapshot:
    snap = GraphSnapshot()
    for row in client.run("MATCH (n:Object) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props"):
        snap.add_node(Node(id=row["id"], type=_node_type(row["labels"]), props=row["props"]))
    for row in client.run(
        "MATCH (a:Object)-[r]->(b:Object) "
        "RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props"
    ):
        props = row["props"] or {}
        snap.add_edge(Edge(id=str(props.get("id") or f"{row['source']}-{row['type']}-{row['target']}"),
                           type=row["type"], source=row["source"], target=row["target"], props=props))
    for row in client.run("MATCH (e:Evidence) RETURN e.id AS id, e.relation_id AS relation_id, properties(e) AS props"):
        snap.add_evidence(Evidence(id=row["id"], relation_id=row["relation_id"], props=row["props"]))
    return snap
