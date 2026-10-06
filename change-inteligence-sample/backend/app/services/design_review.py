"""Design Review (US-07): deterministic REUSE / EXTEND / CREATE recommendation. LLM is optional."""
from __future__ import annotations

import re
from typing import Any

from app.domain.models import CandidateOut, DesignReviewIn, DesignReviewOut, ObjectRef
from app.graph.snapshot import GraphSnapshot, Node
from app.services.common import ref

DEFAULT_RULES: dict[str, Any] = {
    "weights": {"field_overlap": 0.5, "name_overlap": 0.3, "description_overlap": 0.2},
    "thresholds": {"reuse": 0.75, "extend": 0.35},
    "lifecycle_keywords": ["時点", "履歴", "スナップショット", "snapshot", "history", "archive"],
}

_SYNONYMS = {
    "zip": "postal_code", "zipcode": "postal_code", "postcode": "postal_code", "postal": "postal_code",
    "pref": "prefecture", "state": "prefecture", "street": "address1", "addr": "address", "mail": "email",
    "tel": "phone", "cust": "customer",
}


def _tokens(text: str) -> set[str]:
    text = text.lower()
    parts = re.split(r"[^a-z0-9ぁ-んァ-ヶ一-龠]+", text)
    out: set[str] = set()
    for p in parts:
        if not p:
            continue
        out.add(_SYNONYMS.get(p, p))
        # camelCase / snake fragments
        for frag in re.findall(r"[a-z]+|[0-9]+", p):
            if len(frag) > 2:
                out.add(_SYNONYMS.get(frag, frag))
    return out


def _bigrams(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text.lower())
    return {text[i:i + 2] for i in range(len(text) - 1)} if len(text) > 1 else set()


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _norm_field(f: str) -> str:
    f = f.lower().strip()
    return _SYNONYMS.get(f, f)


def _candidate_nodes(snap: GraphSnapshot) -> list[Node]:
    return snap.nodes_of_type("BusinessObject", "Table")


def _fields_of(snap: GraphSnapshot, node: Node) -> set[str]:
    if node.type == "Table":
        return {_norm_field(c) for c in node.props.get("columns", []) or []}
    cols: set[str] = set()
    for e in snap.in_edges(node.id, "REPRESENTS"):
        t = snap.nodes.get(e.source)
        if t:
            cols |= {_norm_field(c) for c in t.props.get("columns", []) or []}
    return cols


def _apis_of(snap: GraphSnapshot, node: Node) -> list[ObjectRef]:
    bo_ids = [node.id] if node.type == "BusinessObject" else [e.target for e in snap.out_edges(node.id, "REPRESENTS")]
    apis: dict[str, ObjectRef] = {}
    for bo in bo_ids:
        for e in snap.in_edges(bo, "OPERATES_ON"):
            if e.source in snap.nodes:
                apis[e.source] = ref(snap.nodes[e.source])
    return list(apis.values())


def _consumers_of(snap: GraphSnapshot, node: Node, apis: list[ObjectRef]) -> list[ObjectRef]:
    cons: dict[str, ObjectRef] = {}
    tables = [node.id] if node.type == "Table" else [e.source for e in snap.in_edges(node.id, "REPRESENTS")]
    for t in tables:
        for e in snap.in_edges(t, "READS") + snap.in_edges(t, "WRITES"):
            n = snap.nodes.get(e.source)
            if n and not (n.type == "Unknown" and n.props.get("status") == "resolved"):
                cons[n.id] = ref(n)
    for a in apis:
        for e in snap.in_edges(a.id, "CALLS"):
            if e.source in snap.nodes:
                cons[e.source] = ref(snap.nodes[e.source])
    return list(cons.values())


def _owners_of(snap: GraphSnapshot, node: Node) -> list[ObjectRef]:
    owners = snap.owners_of(node.id)
    if not owners and node.type == "Table":
        for e in snap.out_edges(node.id, "REPRESENTS"):
            owners += snap.owners_of(e.target)
        for e in snap.in_edges(node.id, "WRITES"):
            owners += snap.owners_of(e.source)
    seen: dict[str, ObjectRef] = {}
    for o in owners:
        seen[o.id] = ref(o)
    return list(seen.values())


def review(snap: GraphSnapshot, req: DesignReviewIn, rules: dict[str, Any] | None = None) -> DesignReviewOut:
    rules = {**DEFAULT_RULES, **(rules or {})}
    w, th = rules["weights"], rules["thresholds"]
    req_fields = {_norm_field(f) for f in req.fields}
    req_name_tokens = _tokens(req.name)
    req_desc_bigrams = _bigrams(req.description) | _bigrams(req.name)

    candidates: list[CandidateOut] = []
    for node in _candidate_nodes(snap):
        fields = _fields_of(snap, node)
        name_tokens = _tokens(node.name) | _tokens(node.id.split(":", 1)[-1])
        desc_bigrams = _bigrams(str(node.props.get("description", ""))) | _bigrams(node.name)

        matched = sorted(req_fields & fields)
        missing = sorted(req_fields - fields)
        extra = sorted(fields - req_fields)
        field_cov = len(matched) / len(req_fields) if req_fields else 0.0  # how much of the request the candidate covers
        field_score = 0.6 * field_cov + 0.4 * _jaccard(req_fields, fields) if req_fields else 0.0
        name_score = _jaccard(req_name_tokens, name_tokens) if req_name_tokens else 0.0
        if req_name_tokens & name_tokens:
            name_score = max(name_score, 0.5)
        desc_score = _jaccard(req_desc_bigrams, desc_bigrams) if req_desc_bigrams else 0.0
        if desc_score > 0:
            desc_score = min(1.0, desc_score * 3)  # bigram jaccard is naturally small
        score = w["field_overlap"] * field_score + w["name_overlap"] * name_score + w["description_overlap"] * desc_score
        if score < 0.05:
            continue
        reasons = []
        if matched:
            reasons.append(f"項目が一致: {', '.join(matched)}")
        if req_name_tokens & name_tokens:
            reasons.append(f"名前が一致: {', '.join(sorted(req_name_tokens & name_tokens))}")
        if desc_score > 0.1:
            reasons.append("説明が似ている")
        apis = _apis_of(snap, node)
        candidates.append(
            CandidateOut(
                id=node.id, type=node.type, name=node.name, score=round(score, 3), matchedFields=matched, missingFields=missing,
                extraFields=extra, owners=_owners_of(snap, node), apis=apis, consumers=_consumers_of(snap, node, apis),
                representedBy=[ref(snap.nodes[e.source]) for e in snap.in_edges(node.id, "REPRESENTS") if e.source in snap.nodes],
                reasons=reasons,
            )
        )
    candidates.sort(key=lambda c: -c.score)
    candidates = candidates[:5]

    rationale: list[str] = []
    alternatives: list[dict[str, str]] = []
    lifecycle_hit = [k for k in rules["lifecycle_keywords"] if k.lower() in (req.description + " " + req.name).lower()]
    top = candidates[0] if candidates else None

    if top is None:
        recommendation, confidence = "CREATE", 0.8
        rationale.append("似ている既存のデータは見つかりませんでした。")
    elif top.score >= th["reuse"] and not top.missingFields and not lifecycle_hit:
        recommendation, confidence = "REUSE", min(0.95, top.score)
        rationale.append(f"{top.name} に必要な項目がすべて揃っています。既存の API 経由で再利用してください。")
    elif top.score >= th["extend"]:
        recommendation, confidence = "EXTEND", min(0.9, 0.5 + top.score / 2)
        rationale.append(f"{top.name} と大きく重なります（類似度 {int(top.score * 100)}%）。"
                         + (f"不足している項目: {', '.join(top.missingFields)}。" if top.missingFields else "必要な項目はすべて存在します。"))
        if lifecycle_hit:
            rationale.append(f"データの性質が異なります（キーワード: {', '.join(lifecycle_hit)}）。今回は「その時点の記録」ですが、"
                             f"{top.name} は常に最新に更新されるマスタです。")
            alternatives.append({"recommendation": "CREATE",
                                 "reason": f"{top.name} を書き換えるのではなく、{req.system or ''} 側に「その時点の記録」用のデータを新設し、{top.name} への参照を持たせる。"})
            confidence = round(min(confidence, 0.65), 2)
        else:
            alternatives.append({"recommendation": "REUSE", "reason": f"不足項目が必須でなければ、{top.name} をそのまま再利用できます。"})
    else:
        recommendation, confidence = "CREATE", 0.7
        rationale.append(f"最も近い {top.name} でも重なりは小さいです（類似度 {int(top.score * 100)}%）。")
        alternatives.append({"recommendation": "EXTEND", "reason": f"意味が同じであれば {top.name} の拡張も検討できます。"})

    if top is not None:
        if top.owners:
            rationale.append(f"相談先: {'、'.join(o.name for o in top.owners)}。")
        else:
            rationale.append(f"{top.name} は責任チームが未設定です。拡張する前に責任チームを決める必要があります。")
        if top.consumers:
            rationale.append(f"{top.name} を現在利用しているもの: {'、'.join(c.name for c in top.consumers)}。")
        if req.system and top.owners and all(req.system.lower() not in (o.name.lower()) for o in top.owners):
            rationale.append(f"追加する側（{req.system}）と責任チームが異なるため、システムをまたぐ変更になります。")

    consult: dict[str, ObjectRef] = {}
    for c in candidates[:3]:
        for o in c.owners:
            consult[o.id] = o
    return DesignReviewOut(recommendation=recommendation, confidence=round(confidence, 2), rationale=rationale,
                           alternatives=alternatives, candidates=candidates, consult=list(consult.values()))
