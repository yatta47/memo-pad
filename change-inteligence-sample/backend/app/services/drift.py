"""Freshness / drift detection: signals computed from Evidence timestamps and observation types.

These are the "please update" nudges derived from data rather than from memory:
- stale:          an observed dependency has not been seen for N days (candidate for removal)
- declared_only:  a dependency is declared (spec / catalog) but never observed in logs
- observed_only:  a dependency is observed in logs but nobody declared it (shadow dependency)
- no_evidence:    a non-owner data/API dependency has no evidence at all
- unknown_open:   an Unknown has stayed unresolved for N days
Each finding names the teams to notify (owners of both ends), which is what makes the nudge actionable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import ObjectRef
from app.graph.snapshot import Edge, GraphSnapshot
from app.services.common import ref

DATA_FLOW = {"CALLS", "READS", "WRITES"}
OBSERVED = {"observed"}
DECLARED = {"declared", "manual"}

DriftKind = Literal["stale", "declared_only", "observed_only", "no_evidence", "unknown_open"]


class DriftOut(BaseModel):
    kind: DriftKind
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    title: str
    detail: str
    relationId: str | None = None
    relation: str | None = None
    source: ObjectRef | None = None
    target: ObjectRef | None = None
    lastSeen: str | None = None
    daysSince: int | None = None
    notify: list[ObjectRef] = Field(default_factory=list)


def _parse(ts: object) -> datetime | None:
    if ts is None:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _owners_of_edge(snap: GraphSnapshot, e: Edge) -> list[ObjectRef]:
    seen: dict[str, ObjectRef] = {}
    for nid in (e.source, e.target):
        for t in snap.owners_of(nid):
            seen[t.id] = ref(t)
        node = snap.nodes.get(nid)
        if node and node.type == "API":  # APIs are owned via the service that provides them
            for pv in snap.in_edges(nid, "PROVIDES"):
                for t in snap.owners_of(pv.source):
                    seen[t.id] = ref(t)
        if node and node.type == "Table":  # tables are owned via the service that writes them / the BO they represent
            for w in snap.in_edges(nid, "WRITES"):
                for t in snap.owners_of(w.source):
                    seen[t.id] = ref(t)
            for r in snap.out_edges(nid, "REPRESENTS"):
                for t in snap.owners_of(r.target):
                    seen[t.id] = ref(t)
    return list(seen.values())


def detect(snap: GraphSnapshot, stale_days: int = 30, now: datetime | None = None) -> list[DriftOut]:
    now = now or datetime.now(timezone.utc)
    out: list[DriftOut] = []

    for e in snap.edges:
        if e.type not in DATA_FLOW:
            continue
        src, tgt = snap.nodes.get(e.source), snap.nodes.get(e.target)
        if src is None or tgt is None:
            continue
        if src.type == "Unknown" and src.props.get("status") == "resolved":
            continue
        is_owner_access = e.props.get("access_mode") == "owner"
        evidence = snap.evidence_for(e.id)
        obs = [ev for ev in evidence if ev.props.get("observation_type") in OBSERVED]
        dec = [ev for ev in evidence if ev.props.get("observation_type") in DECLARED]
        notify = _owners_of_edge(snap, e)
        rel_txt = f"{src.name} → {tgt.name}"

        if not evidence and not is_owner_access:
            out.append(DriftOut(kind="no_evidence", severity="LOW", title="根拠がありません",
                                detail=f"{rel_txt} の関係に根拠（ログ・申告）が 1 件もありません。本当に存在する依存か確認が必要です。",
                                relationId=e.id, relation=e.type, source=ref(src), target=ref(tgt), notify=notify))
            continue

        if obs:
            last = max((d for d in (_parse(ev.props.get("last_seen")) for ev in obs) if d), default=None)
            if last is not None:
                days = (now - last).days
                if days >= stale_days:
                    out.append(DriftOut(kind="stale", severity="MEDIUM", title=f"{days} 日間観測されていません",
                                        detail=f"{rel_txt} は {last.date().isoformat()} を最後にログに現れていません。使われなくなった依存なら、関係の削除（廃止）を検討してください。",
                                        relationId=e.id, relation=e.type, source=ref(src), target=ref(tgt),
                                        lastSeen=last.isoformat(), daysSince=days, notify=notify))

        if obs and not dec and not is_owner_access and src.type != "Unknown":
            direct = e.props.get("access_mode") == "direct"
            out.append(DriftOut(kind="observed_only", severity="HIGH" if direct else "MEDIUM", title="観測されているが申告されていません",
                                detail=f"{rel_txt} はログで観測されていますが、API 仕様書やサービスカタログに申告がありません。" + ("正規ルート外の直接参照でもあります。" if direct else "利用を申告して台帳に載せてください。"),
                                relationId=e.id, relation=e.type, source=ref(src), target=ref(tgt),
                                lastSeen=max((str(ev.props.get("last_seen")) for ev in obs), default=None), notify=notify))

        if dec and not obs and not is_owner_access:
            out.append(DriftOut(kind="declared_only", severity="LOW", title="申告はあるが観測されていません",
                                detail=f"{rel_txt} は申告されていますが、ログでは一度も観測されていません。実際には使われていない可能性があります。",
                                relationId=e.id, relation=e.type, source=ref(src), target=ref(tgt),
                                lastSeen=max((str(ev.props.get("last_seen")) for ev in dec), default=None), notify=notify))

    for u in snap.nodes_of_type("Unknown"):
        if u.props.get("status") == "resolved":
            continue
        edges = snap.out_edges(u.id) + snap.in_edges(u.id)
        firsts = [d for e in edges for d in (_parse(ev.props.get("first_seen")) for ev in snap.evidence_for(e.id)) if d]
        first = min(firsts) if firsts else None
        days = (now - first).days if first else None
        if days is not None and days >= stale_days:
            notify: dict[str, ObjectRef] = {}
            for e in edges:
                for o in _owners_of_edge(snap, e):
                    notify[o.id] = o
            tgt = snap.nodes.get(edges[0].target) if edges else None
            out.append(DriftOut(kind="unknown_open", severity="HIGH", title=f"{days} 日間、正体が分かっていません",
                                detail=f"{u.name} は {first.date().isoformat()} に初めて観測されてから未特定のままです。" + (f"読み取られているのは {tgt.name} です。" if tgt else ""),
                                source=ref(u), target=ref(tgt) if tgt else None, lastSeen=first.isoformat(), daysSince=days, notify=list(notify.values())))

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(out, key=lambda d: (order[d.severity], d.kind, d.title))
