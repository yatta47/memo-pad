from __future__ import annotations

from app.domain.models import EvidenceOut, ObjectRef, RelationOut
from app.graph.snapshot import Edge, Evidence, GraphSnapshot, Node


def ref(node: Node) -> ObjectRef:
    return ObjectRef(id=node.id, type=node.type, name=node.name)


def evidence_out(ev: Evidence) -> EvidenceOut:
    p = ev.props
    conf = p.get("confidence")
    return EvidenceOut(
        id=ev.id,
        relation_id=ev.relation_id,
        source_type=p.get("source_type"),
        source_ref=p.get("source_ref"),
        first_seen=str(p["first_seen"]) if p.get("first_seen") is not None else None,
        last_seen=str(p["last_seen"]) if p.get("last_seen") is not None else None,
        confidence=float(conf) if conf is not None else None,
        observation_type=p.get("observation_type"),
        resolved_from=p.get("resolved_from"),
    )


def relation_out(snap: GraphSnapshot, edge: Edge, perspective: str) -> RelationOut:
    src, tgt = snap.nodes[edge.source], snap.nodes[edge.target]
    return RelationOut(
        id=edge.id,
        type=edge.type,
        source=ref(src),
        target=ref(tgt),
        direction="out" if edge.source == perspective else "in",
        properties={k: v for k, v in edge.props.items() if k != "id"},
        evidence=[evidence_out(e) for e in snap.evidence_for(edge.id)],
    )
