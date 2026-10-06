"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ObjectLink, Rel, TypeBadge } from "@/components/Badges";
import EvidenceList from "@/components/Evidence";
import { api, propLabel, propValue } from "@/lib/api";
import type { ObjectDetail } from "@/lib/types";

export default function ObjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const objectId = decodeURIComponent(id);
  const [obj, setObj] = useState<ObjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.object(objectId).then(setObj).catch((e) => setError(e.message)); }, [objectId]);

  if (error) return <div className="alert danger">{error}</div>;
  if (!obj) return <div className="muted">読み込み中…</div>;
  const outgoing = obj.relations.filter((r) => r.direction === "out");
  const incoming = obj.relations.filter((r) => r.direction === "in");

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="row" style={{ marginBottom: 4 }}><TypeBadge type={obj.type} /><h1>{obj.name}</h1></div>
          <p className="lead"><code>{obj.id}</code></p>
        </div>
        <div className="actions">
          <Link href={`/map?center=${encodeURIComponent(obj.id)}`}><button className="secondary">全体マップで見る</button></Link>
          <Link href={`/impact?object_id=${encodeURIComponent(obj.id)}`}><button>変更影響を分析する</button></Link>
          {obj.type === "Unknown" && <Link href={`/unknowns/${encodeURIComponent(obj.id)}`}><button className="secondary">正体を特定する</button></Link>}
        </div>
      </div>
      <div className="grid cols-2">
        <div className="card">
          <h3>基本情報</h3>
          <div className="kv">
            {Object.entries(obj.properties).map(([k, v]) => (
              <span key={k} style={{ display: "contents" }}><span className="k">{propLabel(k)}</span><span>{Array.isArray(v) ? <span className="chips">{v.map((c) => <span key={String(c)} className="chip">{String(c)}</span>)}</span> : propValue(k, v)}</span></span>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>責任チーム</h3>
          {obj.owners.length === 0 ? <div className="alert warn">責任チームが未設定です。</div> : obj.owners.map((o) => <div key={o.id}><ObjectLink obj={o} /></div>)}
        </div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3>関係（{obj.relations.length}）</h3>
        <table>
          <thead><tr><th>向き</th><th>関係</th><th>相手</th><th>補足</th><th>根拠</th></tr></thead>
          <tbody>
            {[...outgoing, ...incoming].map((r) => {
              const other = r.direction === "out" ? r.target : r.source;
              const direct = r.properties?.access_mode === "direct";
              return (
                <tr key={r.id}>
                  <td>{r.direction === "out" ? "→ この対象から" : "← この対象へ"}</td>
                  <td><Rel type={r.type} />{direct && <span className="badge HIGH" style={{ marginLeft: 6 }}>直接参照</span>}</td>
                  <td><ObjectLink obj={other} /></td>
                  <td className="small muted">{Object.entries(r.properties).filter(([k]) => k !== "access_mode" || !direct).map(([k, v]) => `${propLabel(k)}: ${propValue(k, v)}`).join(" / ") || "—"}</td>
                  <td><EvidenceList items={r.evidence} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
