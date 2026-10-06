"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import GraphView from "@/components/GraphView";
import { ObjectLink, Rel, TypeBadge } from "@/components/Badges";
import { PageHeader } from "@/components/Page";
import { api, TYPE_LABELS, propLabel, propValue } from "@/lib/api";
import type { GraphOut, ObjectRef } from "@/lib/types";

const ALL_TYPES = ["Team", "Service", "API", "BusinessObject", "Database", "Table", "Batch", "Unknown"];

function SystemMapPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [objects, setObjects] = useState<ObjectRef[]>([]);
  const [center, setCenter] = useState(params.get("center") ?? "bo:customer");
  const [depth, setDepth] = useState(Number(params.get("depth") ?? 2));
  const [query, setQuery] = useState("");
  // 業務データ（概念）は既定で非表示。中心に選んだ対象は常に表示される。
  const [types, setTypes] = useState<Set<string>>(new Set(ALL_TYPES.filter((t) => t !== "BusinessObject")));
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.objects().then(setObjects).catch((e) => setError(String(e.message))); }, []);
  useEffect(() => {
    setLoading(true);
    setError(null);
    api.graph(center, depth).then(setGraph).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [center, depth]);

  const filtered = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    const nodes = graph.nodes.filter((n) => n.isCenter || types.has(n.type));
    const ids = new Set(nodes.map((n) => n.id));
    return { nodes, edges: graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) };
  }, [graph, types]);

  const searchHits = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return objects.filter((o) => o.name.toLowerCase().includes(q) || o.id.toLowerCase().includes(q)).slice(0, 8);
  }, [objects, query]);

  const selectedNode = graph?.nodes.find((n) => n.id === selected) ?? null;
  const selectedEdges = graph?.edges.filter((e) => e.source === selected || e.target === selected) ?? [];
  const onOpen = useCallback((id: string) => router.push(`/objects/${encodeURIComponent(id)}`), [router]);

  return (
    <div>
      <PageHeader title="全体マップ" description="選んだ対象を中心に、関係のある システム・API・データ・担当チーム を表示します。アイコンをクリックで概要、ダブルクリックで詳細へ。" />
      <div className="toolbar card tight">
        <div style={{ position: "relative" }}>
          <input placeholder="名称で検索（例: 顧客）" value={query} onChange={(e) => setQuery(e.target.value)} style={{ width: 260 }} />
          {searchHits.length > 0 && (
            <div className="card tight" style={{ position: "absolute", top: 38, left: 0, width: 360, zIndex: 5 }}>
              {searchHits.map((o) => (
                <div key={o.id} className="row" style={{ padding: "4px 2px", cursor: "pointer" }} onClick={() => { setCenter(o.id); setQuery(""); setSelected(null); }}>
                  <TypeBadge type={o.type} /> {o.name} <span className="muted small">{o.id}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <label style={{ margin: 0 }}>中心</label>
        <select value={center} onChange={(e) => { setCenter(e.target.value); setSelected(null); }}>
          {objects.map((o) => <option key={o.id} value={o.id}>{TYPE_LABELS[o.type] ?? o.type}: {o.name}</option>)}
        </select>
        <label style={{ margin: 0 }}>範囲</label>
        <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
          {[1, 2, 3].map((d) => <option key={d} value={d}>{d} 段先まで</option>)}
        </select>
        <span className="spacer" style={{ flex: 1 }} />
        {graph && graph.unknownCount > 0 && <span className="badge HIGH">⚠ 未特定の利用元 {graph.unknownCount} 件</span>}
        {graph && graph.unknownCount === 0 && <span className="badge LOW">未特定の利用元なし</span>}
      </div>
      <div className="toolbar">
        <span className="small muted">表示する種類:</span>
        {ALL_TYPES.map((t) => (
          <label key={t} className="row" style={{ margin: 0, gap: 4, fontSize: 12 }}>
            <input type="checkbox" checked={types.has(t)} onChange={() => setTypes((prev) => { const n = new Set(prev); if (n.has(t)) n.delete(t); else n.add(t); return n; })} />
            {TYPE_LABELS[t]}
          </label>
        ))}
      </div>
      {error && <div className="alert danger">{error}</div>}
      <div className="grid side">
        <div>
          {loading && <div className="muted small" style={{ marginBottom: 6 }}>読み込み中…</div>}
          <GraphView nodes={filtered.nodes} edges={filtered.edges} onSelect={setSelected} onOpen={onOpen} />
        </div>
        <div className="card">
          {!selectedNode && <div className="muted">アイコンをクリックすると概要を表示します。</div>}
          {selectedNode && (
            <div>
              <div className="row"><TypeBadge type={selectedNode.type} /><strong>{selectedNode.name}</strong></div>
              <div className="small muted" style={{ marginTop: 4 }}><code>{selectedNode.id}</code></div>
              <div className="kv" style={{ marginTop: 10 }}>
                {Object.entries(selectedNode.properties).filter(([k]) => !["id", "name"].includes(k)).map(([k, v]) => (
                  <span key={k} style={{ display: "contents" }}><span className="k">{propLabel(k)}</span><span>{propValue(k, v)}</span></span>
                ))}
              </div>
              <h3 style={{ marginTop: 14 }}>この対象の関係（{selectedEdges.length}）</h3>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {selectedEdges.map((e) => {
                  const other = e.source === selected ? e.target : e.source;
                  const o = graph?.nodes.find((n) => n.id === other);
                  return (
                    <li key={e.id} className="small">
                      {e.source === selected ? "→" : "←"} <Rel type={e.type} /> {o ? <ObjectLink obj={o} showType={false} /> : other}
                      {e.properties?.access_mode === "direct" && <span className="badge HIGH" style={{ marginLeft: 6 }}>直接参照</span>}
                    </li>
                  );
                })}
              </ul>
              <div className="row" style={{ marginTop: 14 }}>
                <button className="secondary" onClick={() => setCenter(selectedNode.id)}>ここを中心にする</button>
                <button className="secondary" onClick={() => router.push(`/impact?object_id=${encodeURIComponent(selectedNode.id)}`)}>変更影響を見る</button>
                <button onClick={() => onOpen(selectedNode.id)}>詳細</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="muted">読み込み中…</div>}>
      <SystemMapPage />
    </Suspense>
  );
}
