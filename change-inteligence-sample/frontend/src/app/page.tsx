"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CircleQuestionMark, Database, ShieldAlert, Users, Waypoints } from "lucide";
import GraphView from "@/components/GraphView";
import Icon from "@/components/Icon";
import { ObjectLink, Risk } from "@/components/Badges";
import { PageHeader, StatCard } from "@/components/Page";
import { api, DRIFT_LABELS } from "@/lib/api";
import type { DirectAccess, Drift, GovernanceSummary, GraphOut, UnknownSummary } from "@/lib/types";

const fmt = (v?: string | null) => (v ? v.replace("T", " ").slice(0, 10) : "—");

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<GovernanceSummary | null>(null);
  const [drift, setDrift] = useState<Drift[]>([]);
  const [direct, setDirect] = useState<DirectAccess[]>([]);
  const [unknowns, setUnknowns] = useState<UnknownSummary[]>([]);
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.governance(), api.drift(30), api.directAccess(), api.unknowns("open"), api.graph("bo:customer", 2)])
      .then(([s, d, da, u, g]) => { setSummary(s); setDrift(d); setDirect(da); setUnknowns(u); setGraph(g); })
      .catch((e) => setError(e.message));
  }, []);
  const onOpen = useCallback((id: string) => router.push(`/objects/${encodeURIComponent(id)}`), [router]);

  const attention = [
    ...drift.filter((d) => d.severity === "HIGH").map((d) => ({ key: `drift-${d.relationId ?? d.source?.id}-${d.kind}`, severity: d.severity, kind: DRIFT_LABELS[d.kind]?.label ?? d.kind, title: d.title, detail: d.detail, href: "/governance#drift", teams: d.notify })),
    ...direct.filter((d) => d.severity === "HIGH").map((d) => ({ key: `da-${d.relationId}`, severity: d.severity, kind: "正規ルート外のデータ参照", title: `${d.source.name} が ${d.target.name} を直接参照`, detail: d.bypassesApi ? "本来使うべき API を既に呼んでいるのに迂回しています。" : d.note ?? "", href: "/governance", teams: [...d.sourceOwners, ...d.targetOwners] })),
  ].slice(0, 6);

  const mapNodes = graph ? graph.nodes.filter((n) => n.isCenter || n.type !== "BusinessObject") : [];
  const mapIds = new Set(mapNodes.map((n) => n.id));
  const mapEdges = graph ? graph.edges.filter((e) => mapIds.has(e.source) && mapIds.has(e.target)) : [];

  return (
    <div>
      <PageHeader
        title="ダッシュボード"
        description="システム間の依存関係を一枚の地図に。変更の前に「何に影響するか」「誰に相談すべきか」「ルールから外れているものはないか」を確認できます。"
        actions={<><Link href="/impact"><button>変更影響を分析する</button></Link><Link href="/design-review"><button className="secondary">新規データをレビューする</button></Link></>}
      />
      {error && <div className="alert danger">{error}</div>}
      <div className="stat-grid">
        <StatCard label="登録されている対象" value={summary?.objectCount ?? "—"} hint={summary ? `関係 ${summary.relationCount} 件` : ""} tone="accent" icon={Database} href="/map" />
        <StatCard label="正規ルート外のデータ参照" value={summary?.directAccessCount ?? "—"} hint={summary ? `高 ${summary.directAccessBySeverity.HIGH ?? 0} / 中 ${summary.directAccessBySeverity.MEDIUM ?? 0}` : ""} tone="danger" icon={ShieldAlert} href="/governance" />
        <StatCard label="未特定の利用元" value={summary?.unknownOpen ?? "—"} hint={summary ? `特定済み ${summary.unknownResolved}` : ""} tone={summary?.unknownOpen ? "danger" : "ok"} icon={CircleQuestionMark} href="/unknowns" />
        <StatCard label="責任チーム未設定" value={summary?.ownerMissing.length ?? "—"} hint="相談先が決まらない対象" tone="warn" icon={Users} href="/governance" />
        <StatCard label="台帳と実態のズレ" value={drift.length} hint={`高 ${drift.filter((d) => d.severity === "HIGH").length} · 30 日基準`} tone={drift.some((d) => d.severity === "HIGH") ? "danger" : "warn"} icon={AlertTriangle} href="/governance#drift" />
      </div>

      <div className="grid dash">
        <div className="card flush">
          <div className="card-head"><h3>今すぐ確認したいこと</h3><Link className="more" href="/governance">ルール逸脱の確認へ →</Link></div>
          {attention.length === 0 ? <div className="empty">リスク高の項目はありません。</div> : (
            <table>
              <thead><tr><th>リスク</th><th>種類</th><th>内容</th><th>相談先</th></tr></thead>
              <tbody>
                {attention.map((a) => (
                  <tr key={a.key}>
                    <td><Risk level={a.severity} /></td>
                    <td><span className="badge outline">{a.kind}</span></td>
                    <td><Link href={a.href}><strong>{a.title}</strong></Link><div className="small muted">{a.detail}</div></td>
                    <td>{Array.from(new Map(a.teams.map((t) => [t.id, t])).values()).map((t) => <div key={t.id}><ObjectLink obj={t} showType={false} /></div>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="card flush">
          <div className="card-head"><h3>未特定の利用元</h3><Link className="more" href="/unknowns">一覧へ →</Link></div>
          {unknowns.length === 0 ? <div className="empty">未特定の利用元はありません。</div> : (
            <ul className="list" style={{ padding: "0 20px" }}>
              {unknowns.map((u) => (
                <li key={u.id}>
                  <span style={{ color: "#ea580c", marginTop: 2 }}><Icon node={CircleQuestionMark} size={18} /></span>
                  <div style={{ flex: 1 }}>
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <Link href={`/unknowns/${encodeURIComponent(u.id)}`}><strong>{u.name}</strong></Link>
                      <span className="meta">最終観測 {fmt(u.lastSeen)}</span>
                    </div>
                    <div className="small muted">{u.hint}</div>
                    <div className="meta" style={{ marginTop: 4 }}>根拠 {u.evidenceCount} 件 · <Link href={`/unknowns/${encodeURIComponent(u.id)}`}>正体を特定する</Link></div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <h3><Icon node={Waypoints} size={14} className="icon" />Customer まわりの全体像</h3>
          <Link className="more" href="/map?center=bo%3Acustomer">全体マップで開く →</Link>
        </div>
        {graph ? <GraphView nodes={mapNodes} edges={mapEdges} onOpen={onOpen} compact /> : <div className="empty">読み込み中…</div>}
      </div>
    </div>
  );
}
