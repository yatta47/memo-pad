"""Impact Analysis (US-01, US-02, US-06, US-08) — deterministic graph traversal over a snapshot."""
from __future__ import annotations

from collections import deque
from typing import Any

from app.domain.models import AffectedOut, ChangeType, ImpactOut, ObjectRef
from app.graph.snapshot import Edge, GraphSnapshot, Node
from app.services.common import ref

DEFAULT_RULES: dict[str, Any] = {
    "max_depth": 4,
    "traversal": {
        "Table": [{"relation": "READS", "direction": "in"}, {"relation": "WRITES", "direction": "in"}, {"relation": "REPRESENTS", "direction": "out"}],
        "BusinessObject": [{"relation": "OPERATES_ON", "direction": "in"}, {"relation": "DEPENDS_ON", "direction": "in"}],
        "API": [{"relation": "CALLS", "direction": "in"}, {"relation": "PROVIDES", "direction": "in"}],
        "Service": [{"relation": "PROVIDES", "direction": "out"}],
    },
    "direct_relations": ["READS", "WRITES", "CALLS", "PROVIDES"],
    "non_blocking_inbound": ["OWNS", "PROVIDES"],
    "risk": {"high_if_unknown": True, "high_if_direct_db_access": True, "high_if_affected_services_at_least": 3, "medium_if_affected_at_least": 1},
}


def _is_active(node: Node) -> bool:
    return not (node.type == "Unknown" and node.props.get("status") == "resolved")


def _steps(snap: GraphSnapshot, node: Node, rules: dict[str, Any], arrived: tuple[str, str] | None = None) -> list[tuple[Edge, str]]:
    """Return (edge, next_node_id) pairs to follow from `node` according to traversal rules.

    `arrived` is (relation, direction) of the hop that reached `node`. Following the same relation type
    straight back in the opposite direction is skipped: e.g. API <-PROVIDES- Service -PROVIDES-> sibling API
    would otherwise mark every sibling API as impacted.
    """
    out: list[tuple[Edge, str]] = []
    for step in rules["traversal"].get(node.type, []):
        if arrived and step["relation"] == arrived[0] and step["direction"] != arrived[1]:
            continue
        if step["direction"] == "in":
            out += [(e, e.source) for e in snap.in_edges(node.id, step["relation"])]
        else:
            out += [(e, e.target) for e in snap.out_edges(node.id, step["relation"])]
    return out


def analyze(snap: GraphSnapshot, object_id: str, change_type: ChangeType, rules: dict[str, Any] | None = None) -> ImpactOut | None:
    rules = {**DEFAULT_RULES, **(rules or {})}
    target = snap.nodes.get(object_id)
    if target is None:
        return None

    if change_type == "delete":
        return _analyze_delete(snap, target, rules)

    max_depth = int(rules.get("max_depth", 4))
    direct_relations = set(rules.get("direct_relations", []))

    # BFS: record shortest path (relation types + node ids) to each reached node.
    visited: dict[str, dict[str, Any]] = {target.id: {"path": [], "via": [], "depth": 0, "edge": None, "arrived": None}}
    queue: deque[str] = deque([target.id])
    while queue:
        cur_id = queue.popleft()
        cur = visited[cur_id]
        if cur["depth"] >= max_depth:
            continue
        for edge, nxt_id in _steps(snap, snap.nodes[cur_id], rules, cur["arrived"]):
            nxt = snap.nodes.get(nxt_id)
            if nxt is None or not _is_active(nxt) or nxt_id in visited:
                continue
            direction = "in" if edge.target == cur_id else "out"
            visited[nxt_id] = {"path": cur["path"] + [edge.type], "via": cur["via"] + [nxt_id], "depth": cur["depth"] + 1,
                               "edge": edge, "arrived": (edge.type, direction)}
            queue.append(nxt_id)

    affected: list[AffectedOut] = []
    for nid, info in visited.items():
        if nid == target.id:
            continue
        node = snap.nodes[nid]
        if node.type in ("Team",):
            continue
        edge: Edge = info["edge"]
        affected.append(
            AffectedOut(
                id=nid, type=node.type, name=node.name, path=info["path"], via=info["via"], depth=info["depth"],
                direct=info["depth"] == 1 and edge.type in direct_relations,
                owners=[ref(t) for t in snap.owners_of(nid)],
                accessMode=edge.props.get("access_mode") if edge.type in ("READS", "WRITES") else None,
                evidenceCount=len(snap.evidence_for(edge.id)),
            )
        )
    affected.sort(key=lambda a: (not a.direct, a.depth, a.type, a.name))

    warnings, unknown_count, owners = _assess(snap, target, affected, rules)
    risk = _risk(affected, unknown_count, warnings, rules)
    summary = _summary(target, change_type, affected, owners, unknown_count)
    return ImpactOut(
        target=target.id, targetName=target.name, targetType=target.type, changeType=change_type, risk=risk,
        affected=affected, owners=[o.id for o in owners], ownerDetails=owners, unknownCount=unknown_count,
        warnings=warnings, canDelete=None, summary=summary,
    )


def _analyze_delete(snap: GraphSnapshot, target: Node, rules: dict[str, Any]) -> ImpactOut:
    non_blocking = set(rules.get("non_blocking_inbound", ["OWNS", "PROVIDES"]))
    direct_relations = set(rules.get("direct_relations", []))
    affected: list[AffectedOut] = []
    for e in snap.in_edges(target.id):
        if e.type == "OWNS":
            continue
        src = snap.nodes.get(e.source)
        if src is None or not _is_active(src):
            continue
        blocking = e.type not in non_blocking and e.type in direct_relations  # PROVIDES = provider, informational only
        affected.append(
            AffectedOut(
                id=src.id, type=src.type, name=src.name, path=[e.type], via=[src.id], depth=1,
                direct=blocking, owners=[ref(t) for t in snap.owners_of(src.id)],
                accessMode=e.props.get("access_mode") if e.type in ("READS", "WRITES") else None,
                evidenceCount=len(snap.evidence_for(e.id)),
            )
        )
    # Deleting a Table also removes the physical representation of a Business Object.
    for e in snap.out_edges(target.id, "REPRESENTS"):
        bo = snap.nodes.get(e.target)
        if bo is not None:
            affected.append(AffectedOut(id=bo.id, type=bo.type, name=bo.name, path=["REPRESENTS"], via=[bo.id], depth=1, direct=False,
                                        owners=[ref(t) for t in snap.owners_of(bo.id)]))
    affected.sort(key=lambda a: (not a.direct, a.type, a.name))
    warnings, unknown_count, owners = _assess(snap, target, affected, rules)
    blocking = [a for a in affected if a.direct]
    can_delete = not blocking and unknown_count == 0
    if blocking:
        warnings.insert(0, f"利用している先があります: {len(blocking)} 件が影響を受けます")
    if can_delete:
        warnings.append("利用している先はありません。廃止できる見込みです（責任チームへの確認は必要）")
    risk = "LOW" if can_delete else ("HIGH" if unknown_count or len(blocking) >= 2 else "MEDIUM")
    summary = (f"{target.name} は廃止できます。利用している先はありません。" if can_delete
               else f"{target.name} を利用している先が {len(blocking)} 件あります" + (f"（うち正体不明 {unknown_count} 件）。" if unknown_count else "。"))
    return ImpactOut(
        target=target.id, targetName=target.name, targetType=target.type, changeType="delete", risk=risk, affected=affected,
        owners=[o.id for o in owners], ownerDetails=owners, unknownCount=unknown_count, warnings=warnings, canDelete=can_delete, summary=summary,
    )


def _assess(snap: GraphSnapshot, target: Node, affected: list[AffectedOut], rules: dict[str, Any]) -> tuple[list[str], int, list[ObjectRef]]:
    warnings: list[str] = []
    unknown_count = sum(1 for a in affected if a.type == "Unknown")
    direct_db = [a for a in affected if a.accessMode == "direct" and a.type != "Unknown"]
    if direct_db:
        names = ", ".join(a.name for a in direct_db)
        warnings.append(f"正規ルート外のデータ参照があります（{names}）")
    if unknown_count:
        warnings.append(f"正体が分かっていない利用元があります（{unknown_count} 件）")
    owner_required = set(rules.get("owner_required_for", ["Service", "Batch", "BusinessObject"]))
    for a in affected:
        if a.type in owner_required and not a.owners:
            warnings.append(f"責任チームが未設定です: {a.name}")

    owners: dict[str, ObjectRef] = {}
    for t in _target_owners(snap, target):
        owners[t.id] = ref(t)
    for a in affected:
        for o in a.owners:
            owners[o.id] = o
    return warnings, unknown_count, sorted(owners.values(), key=lambda o: o.name)


def _target_owners(snap: GraphSnapshot, target: Node) -> list[Node]:
    direct = snap.owners_of(target.id)
    if direct:
        return direct
    found: dict[str, Node] = {}
    if target.type == "Table":
        for e in snap.in_edges(target.id, "WRITES"):
            for t in snap.owners_of(e.source):
                found[t.id] = t
        for e in snap.out_edges(target.id, "REPRESENTS"):
            for t in snap.owners_of(e.target):
                found[t.id] = t
    elif target.type == "API":
        for e in snap.in_edges(target.id, "PROVIDES"):
            for t in snap.owners_of(e.source):
                found[t.id] = t
    return list(found.values())


def _risk(affected: list[AffectedOut], unknown_count: int, warnings: list[str], rules: dict[str, Any]) -> str:
    r = rules.get("risk", {})
    services = [a for a in affected if a.type in ("Service", "Batch")]
    if r.get("high_if_unknown", True) and unknown_count:
        return "HIGH"
    if r.get("high_if_direct_db_access", True) and any(w.startswith("正規ルート外") for w in warnings):
        return "HIGH"
    if len(services) >= int(r.get("high_if_affected_services_at_least", 3)):
        return "HIGH"
    if len(affected) >= int(r.get("medium_if_affected_at_least", 1)):
        return "MEDIUM"
    return "LOW"


def _summary(target: Node, change_type: str, affected: list[AffectedOut], owners: list[ObjectRef], unknown_count: int) -> str:
    direct = [a for a in affected if a.direct]
    svc = [a for a in affected if a.type in ("Service", "Batch")]
    kind = {"schema_change": "テーブル／項目の変更", "api_change": "API の変更", "delete": "廃止"}.get(change_type, change_type)
    return (f"{target.name} の{kind}: 影響 {len(affected)} 件（直接 {len(direct)}、アプリ／バッチ {len(svc)}、正体不明 {unknown_count}）。"
            f"相談先 {len(owners)} チーム。")
