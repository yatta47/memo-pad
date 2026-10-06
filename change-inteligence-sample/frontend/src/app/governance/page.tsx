"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ObjectLink, Rel, Risk } from "@/components/Badges";
import { PageHeader, StatCard } from "@/components/Page";
import EvidenceList from "@/components/Evidence";
import { api, DRIFT_LABELS } from "@/lib/api";
import type { DirectAccess, Drift, GovernanceSummary } from "@/lib/types";

const fmt = (v?: string | null) => (v ? v.replace("T", " ").slice(0, 10) : "—");

export default function GovernancePage() {
  const [summary, setSummary] = useState<GovernanceSummary | null>(null);
  const [rows, setRows] = useState<DirectAccess[]>([]);
  const [drift, setDrift] = useState<Drift[]>([]);
  const [staleDays, setStaleDays] = useState(30);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.governance(), api.directAccess()]).then(([s, r]) => { setSummary(s); setRows(r); }).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { api.drift(staleDays).then(setDrift).catch((e) => setError(e.message)); }, [staleDays]);
  const driftHigh = drift.filter((d) => d.severity === "HIGH").length;

  return (
    <div>
      <PageHeader title="ルール逸脱の確認" description="正規の API を通さずにデータベースを直接参照しているもの、責任チームが決まっていないもの、正体が分かっていない利用元に加え、台帳と実態のズレ（鮮度・申告漏れ）をまとめて確認します。" />
      {error && <div className="alert danger">{error}</div>}
      {summary && (
        <div className="stat-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
          <StatCard label="台帳と実態のズレ" value={drift.length} hint={`高 ${driftHigh} · ${staleDays} 日基準`} tone={driftHigh ? "danger" : "warn"} href="#drift" />
          <StatCard label="正規ルート外のデータ参照" value={summary.directAccessCount} hint={`高 ${summary.directAccessBySeverity.HIGH ?? 0} / 中 ${summary.directAccessBySeverity.MEDIUM ?? 0}`} tone="danger" href="#direct" />
          <StatCard label="責任チーム未設定" value={summary.ownerMissing.length} hint="相談先が決まらない対象" tone="warn" href="#owner" />
          <StatCard label="未特定の利用元" value={summary.unknownOpen} hint={`特定済み ${summary.unknownResolved}`} tone={summary.unknownOpen ? "danger" : "ok"} href="/unknowns" />
        </div>
      )}
      <div className="card" style={{ marginBottom: 16 }} id="drift">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>鮮度・ズレ（台帳と実態の食い違い）</h3>
          <label className="row" style={{ margin: 0, gap: 6 }}>観測が途絶えたとみなす日数
            <select value={staleDays} onChange={(e) => setStaleDays(Number(e.target.value))}>
              {[14, 30, 60, 90, 180].map((d) => <option key={d} value={d}>{d} 日</option>)}
            </select>
          </label>
        </div>
        <div className="small muted" style={{ marginBottom: 8 }}>
          根拠の「初回観測 / 最終観測」と「申告 / 観測」の区別から機械的に算出しています。通知先はその関係の両端の責任チームです。将来はこの一覧を週次で各チームに送る想定です。
        </div>
        <table>
          <thead><tr><th>種類</th><th>リスク</th><th>内容</th><th>対象</th><th>最終観測 / 経過</th><th>通知先</th></tr></thead>
          <tbody>
            {drift.length === 0 && <tr><td colSpan={6} className="muted">この条件で検知されたズレはありません。</td></tr>}
            {drift.map((d, i) => (
              <tr key={`${d.kind}-${d.relationId ?? d.source?.id}-${i}`}>
                <td><span className="badge outline" title={DRIFT_LABELS[d.kind]?.hint}>{DRIFT_LABELS[d.kind]?.label ?? d.kind}</span></td>
                <td><Risk level={d.severity} /></td>
                <td><strong>{d.title}</strong><div className="small muted">{d.detail}</div></td>
                <td>
                  {d.source && <div><ObjectLink obj={d.source} /></div>}
                  {d.relation && d.target && <div className="small muted" style={{ margin: "2px 0 2px 8px" }}>↓ <Rel type={d.relation} /></div>}
                  {d.target && <div><ObjectLink obj={d.target} /></div>}
                </td>
                <td className="small">{fmt(d.lastSeen)}{d.daysSince != null && <div className="muted">{d.daysSince} 日経過</div>}</td>
                <td>{d.notify.length ? d.notify.map((o) => <div key={o.id}><ObjectLink obj={o} showType={false} /></div>) : <span className="badge warn">責任チーム未設定</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card" style={{ marginBottom: 16 }} id="direct">
        <h3>正規ルート外のデータ参照</h3>
        <table>
          <thead><tr><th>リスク</th><th>参照している側</th><th>アクセス</th><th>参照されているテーブル</th><th>本来使うべき API</th><th>補足</th><th>根拠</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.relationId}>
                <td><Risk level={r.severity} /></td>
                <td><ObjectLink obj={r.source} />{r.sourceOwners.length > 0 && <div className="small muted">責任: {r.sourceOwners.map((o) => o.name).join(", ")}</div>}</td>
                <td><Rel type={r.relation} /> <span className="badge warn">直接参照</span></td>
                <td><ObjectLink obj={r.target} />{r.targetOwners.length > 0 && <div className="small muted">責任: {r.targetOwners.map((o) => o.name).join(", ")}</div>}</td>
                <td>
                  {r.canonicalApis.length === 0 ? <span className="muted small">該当する API がありません</span> : r.canonicalApis.map((a) => <div key={a.id}><ObjectLink obj={a} showType={false} /></div>)}
                  {r.bypassesApi && <div className="badge HIGH" style={{ marginTop: 4 }}>この API を既に使っているのに迂回</div>}
                </td>
                <td className="small">{r.note ?? "—"}</td>
                <td><EvidenceList items={r.evidence} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {summary && (
        <div className="card" id="owner">
          <h3>責任チーム未設定</h3>
          {summary.ownerMissing.length === 0 ? <span className="muted">なし</span> : (
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {summary.ownerMissing.map((o) => <li key={o.id} style={{ marginBottom: 4 }}><ObjectLink obj={o} /> <span className="small muted">— 責任を持つチームが登録されていません</span></li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
