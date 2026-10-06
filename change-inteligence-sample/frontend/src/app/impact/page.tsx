"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import GraphView from "@/components/GraphView";
import { ObjectLink, Path, Risk, TypeBadge } from "@/components/Badges";
import { PageHeader } from "@/components/Page";
import { api, CHANGE_LABELS, TYPE_LABELS } from "@/lib/api";
import type { ChangeType, GraphOut, ImpactOut, ObjectRef } from "@/lib/types";

const CHANGE_TYPES = Object.keys(CHANGE_LABELS) as ChangeType[];

function ImpactPage() {
  const params = useSearchParams();
  const router = useRouter();
  const [objects, setObjects] = useState<ObjectRef[]>([]);
  const [objectId, setObjectId] = useState(params.get("object_id") ?? "table:customer.customer");
  const [changeType, setChangeType] = useState<ChangeType>((params.get("change_type") as ChangeType) ?? "schema_change");
  const [result, setResult] = useState<ImpactOut | null>(null);
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.objects({ type: ["Table", "API", "BusinessObject", "Service", "Batch"] }).then(setObjects).catch((e) => setError(e.message)); }, []);

  const run = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [r, g] = await Promise.all([api.impact(objectId, changeType), api.graph(objectId, 3)]);
      setResult(r); setGraph(g);
      router.replace(`/impact?object_id=${encodeURIComponent(objectId)}&change_type=${changeType}`);
    } catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }, [objectId, changeType, router]);

  useEffect(() => { run(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const highlight = useMemo(() => result ? new Set([result.target, ...result.affected.map((a) => a.id)]) : undefined, [result]);
  const onOpen = useCallback((id: string) => router.push(`/objects/${encodeURIComponent(id)}`), [router]);
  const selectedType = objects.find((o) => o.id === objectId)?.type;
  useEffect(() => {
    if (selectedType === "API" && changeType === "schema_change") setChangeType("api_change");
    if (selectedType === "Table" && changeType === "api_change") setChangeType("schema_change");
  }, [selectedType]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <PageHeader title="変更影響分析" description="変更しようとしている対象から、影響が及ぶ システム・API・データ と、その責任チームを洗い出します。「直接」は変更対象を直接使っているもの、「間接」はその先で影響を受けるものです。" />
      <div className="toolbar card tight">
        <label style={{ margin: 0 }}>変更対象</label>
        <select value={objectId} onChange={(e) => setObjectId(e.target.value)} style={{ minWidth: 320 }}>
          {objects.map((o) => <option key={o.id} value={o.id}>{TYPE_LABELS[o.type] ?? o.type}: {o.name}</option>)}
        </select>
        <label style={{ margin: 0 }}>変更の種類</label>
        <select value={changeType} onChange={(e) => setChangeType(e.target.value as ChangeType)}>
          {CHANGE_TYPES.map((c) => <option key={c} value={c}>{CHANGE_LABELS[c].label} — {CHANGE_LABELS[c].hint}</option>)}
        </select>
        <button onClick={run} disabled={loading}>{loading ? "分析中…" : "分析する"}</button>
      </div>
      {error && <div className="alert danger">{error}</div>}
      {result && (
        <>
          <div className="grid cols-3" style={{ marginBottom: 16 }}>
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div><TypeBadge type={result.targetType} /> <strong>{result.targetName}</strong></div>
                <Risk level={result.risk} />
              </div>
              <div className="small muted" style={{ marginTop: 6 }}>{result.summary}</div>
              {result.canDelete != null && (
                <div className={`alert ${result.canDelete ? "ok" : "danger"}`} style={{ marginTop: 10, marginBottom: 0 }}>
                  {result.canDelete ? "廃止できます: 利用している先はありません" : "廃止できません: 利用している先があります"}
                </div>
              )}
            </div>
            <div className="card">
              <h3>注意事項</h3>
              {result.warnings.length === 0 ? <span className="muted small">なし</span> : result.warnings.map((w, i) => (
                <div key={i} className={`alert ${w.startsWith("利用している先はありません") ? "ok" : w.startsWith("責任チームが未設定") ? "warn" : "danger"}`} style={{ marginBottom: 6 }}>{w}</div>
              ))}
              {result.unknownCount > 0 && <a href="/unknowns" className="small">→ 未特定の利用元を特定する</a>}
            </div>
            <div className="card">
              <h3>相談すべき担当チーム</h3>
              {result.ownerDetails.length === 0 ? <span className="muted small">責任チームが見つかりません</span> : result.ownerDetails.map((o) => <div key={o.id} style={{ marginBottom: 4 }}><ObjectLink obj={o} /></div>)}
            </div>
          </div>
          <div className="grid side" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div className="card">
              <h3>影響を受ける対象（{result.affected.length}） · 未特定 {result.unknownCount}</h3>
              <table>
                <thead><tr><th>対象</th><th>影響</th><th>影響の経路</th><th>責任チーム</th></tr></thead>
                <tbody>
                  {result.affected.map((a) => (
                    <tr key={a.id}>
                      <td><ObjectLink obj={a} /></td>
                      <td>
                        <span className={`badge ${a.direct ? "HIGH" : "info"}`}>{a.direct ? "直接" : "間接"}</span>
                        {a.accessMode === "direct" && <span className="badge warn" style={{ marginLeft: 4 }}>正規ルート外</span>}
                        {a.type === "Unknown" && <span className="badge warn" style={{ marginLeft: 4 }}>未特定</span>}
                      </td>
                      <td><Path hops={a.path} /></td>
                      <td>{a.owners.length ? a.owners.map((o) => <div key={o.id}><ObjectLink obj={o} showType={false} /></div>) : <span className="badge warn">未設定</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              {graph && <GraphView nodes={graph.nodes} edges={graph.edges} highlight={highlight} onOpen={onOpen} />}
              <div className="small muted" style={{ marginTop: 6 }}>濃く表示されているものが影響範囲です。薄いものは関係はあるが影響は及ばない対象です。</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="muted">読み込み中…</div>}>
      <ImpactPage />
    </Suspense>
  );
}
