"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader, StatCard } from "@/components/Page";
import { api, STATUS_LABELS, UNKNOWN_TYPE_LABELS } from "@/lib/api";
import type { UnknownSummary } from "@/lib/types";

const fmt = (v?: string | null) => (v ? v.replace("T", " ").slice(0, 16) : "—");

export default function UnknownInboxPage() {
  const [status, setStatus] = useState<"open" | "resolved" | "all">("open");
  const [items, setItems] = useState<UnknownSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.unknowns(status).then(setItems).catch((e) => setError(e.message)); }, [status]);

  return (
    <div>
      <PageHeader title="未特定の利用元" description="データや API を使っていることは観測されたものの、どのシステム・誰の管理か分かっていないもの。消さずに残し、根拠を確認して正体を特定します。" />
      <div className="toolbar">
        {(["open", "resolved", "all"] as const).map((s) => (
          <button key={s} className={status === s ? "" : "secondary"} onClick={() => setStatus(s)}>{STATUS_LABELS[s]}</button>
        ))}
      </div>
      {error && <div className="alert danger">{error}</div>}
      <div className="card">
        <table>
          <thead><tr><th>ID</th><th>種別</th><th>状態</th><th>手がかり</th><th>関係</th><th>根拠</th><th>最終観測</th><th></th></tr></thead>
          <tbody>
            {items.length === 0 && <tr><td colSpan={8} className="muted">「{STATUS_LABELS[status]}」の未特定はありません。</td></tr>}
            {items.map((u) => (
              <tr key={u.id}>
                <td><Link href={`/unknowns/${encodeURIComponent(u.id)}`}><strong>{u.name}</strong></Link></td>
                <td><span className="badge outline">{UNKNOWN_TYPE_LABELS[u.unknown_type ?? ""] ?? u.unknown_type ?? "—"}</span></td>
                <td><span className={`badge ${u.status === "open" ? "HIGH" : "LOW"}`}>{STATUS_LABELS[u.status] ?? u.status}</span>{u.resolvedTo && <div className="small muted">→ {u.resolvedTo}</div>}</td>
                <td className="small">{u.hint}</td>
                <td>{u.relationCount}</td>
                <td>{u.evidenceCount}</td>
                <td className="small muted">{fmt(u.lastSeen)}</td>
                <td><Link href={`/unknowns/${encodeURIComponent(u.id)}`}><button className="secondary">{u.status === "open" ? "特定する" : "詳細"}</button></Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
