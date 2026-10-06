"""Object detail and neighbourhood graph (US-03)."""
from __future__ import annotations

from app.domain.models import GraphEdge, GraphNode, GraphOut, ObjectDetail, ObjectRef
from app.graph import client
from app.graph.snapshot import GraphSnapshot, _node_type
from app.services.common import ref, relation_out

GRAPH_LIMIT = 300


def list_objects(snap: GraphSnapshot, types: list[str] | None = None, q: str | None = None) -> list[ObjectRef]:
    out = []
    for n in snap.active_nodes():
        if types and n.type not in types:
            continue
        if q and q.lower() not in n.name.lower() and q.lower() not in n.id.lower():
            continue
        out.append(ref(n))
    return sorted(out, key=lambda r: (r.type, r.name))


def get_object(snap: GraphSnapshot, object_id: str) -> ObjectDetail | None:
    node = snap.nodes.get(object_id)
    if node is None:
        return None
    rels = [relation_out(snap, e, object_id) for e in snap.out_edges(object_id)]
    rels += [relation_out(snap, e, object_id) for e in snap.in_edges(object_id)]
    return ObjectDetail(
        id=node.id,
        type=node.type,
        name=node.name,
        properties={k: v for k, v in node.props.items() if k not in ("id",)},
        owners=[ref(t) for t in snap.owners_of(object_id)],
        relations=rels,
    )


def neighbourhood(object_id: str, depth: int = 2, include_resolved: bool = False) -> GraphOut | None:
    """Cypher-based neighbourhood (design §9.1). Never returns the whole graph by default."""
    depth = max(1, min(int(depth), 3))
    center = client.run("MATCH (n:Object {id: $id}) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props", id=object_id)
    if not center:
        return None
    resolved_filter = "" if include_resolved else "AND NONE(x IN nodes(p) WHERE x:Unknown AND x.status = 'resolved' AND x.id <> $id) "
    # 1) nodes within `depth` hops of the center (design §9.1, bounded by LIMIT)
    rows = client.run(
        f"MATCH p=(n:Object {{id: $id}})-[*1..{depth}]-(m:Object) "
        f"WHERE m.id <> $id {resolved_filter}"
        "WITH p LIMIT $limit "
        "UNWIND nodes(p) AS x "
        "WITH collect(DISTINCT x) AS xs "
        "RETURN [x IN xs | {id: x.id, labels: labels(x), props: properties(x)}] AS nodes",
        id=object_id,
        limit=GRAPH_LIMIT,
    )
    nodes: dict[str, GraphNode] = {}
    c = center[0]
    nodes[c["id"]] = GraphNode(id=c["id"], type=_node_type(c["labels"]), name=c["props"].get("name", c["id"]), properties=c["props"], isCenter=True)
    if rows and rows[0]["nodes"]:
        for x in rows[0]["nodes"]:
            if x["id"] not in nodes:
                nodes[x["id"]] = GraphNode(id=x["id"], type=_node_type(x["labels"]), name=x["props"].get("name", x["id"]), properties=x["props"])
    # 2) every relation among the visible nodes (induced subgraph), not only the ones on paths from the center,
    #    so e.g. Team -> Service is drawn even when both were reached through different paths.
    edges: dict[str, GraphEdge] = {}
    for r in client.run(
        "MATCH (a:Object)-[r]->(b:Object) WHERE a.id IN $ids AND b.id IN $ids "
        "RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props",
        ids=list(nodes.keys()),
    ):
        rid = str((r["props"] or {}).get("id") or f"{r['source']}-{r['type']}-{r['target']}")
        edges[rid] = GraphEdge(id=rid, type=r["type"], source=r["source"], target=r["target"], properties=r["props"] or {})
    unknown_count = sum(1 for n in nodes.values() if n.type == "Unknown" and n.properties.get("status") != "resolved")
    return GraphOut(center=object_id, depth=depth, nodes=list(nodes.values()), edges=list(edges.values()), unknownCount=unknown_count,
                    truncated=len(nodes) >= GRAPH_LIMIT)
