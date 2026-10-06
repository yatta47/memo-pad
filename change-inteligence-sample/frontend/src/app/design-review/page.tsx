"use client";

import { useState } from "react";
import { ObjectLink, TypeBadge } from "@/components/Badges";
import { PageHeader, StatCard } from "@/components/Page";
import { api } from "@/lib/api";
import type { DesignReviewOut } from "@/lib/types";

const REC_LABELS: Record<string, string> = { REUSE: "既存を再利用", EXTEND: "既存を拡張", CREATE: "新規に作成" };

export default function DesignReviewPage() {
  const [name, setName] = useState("shipping_address");
  const [description, setDescription] = useState("注文時点の配送先住所を保存したい");
  const [fields, setFields] = useState("postal_code, prefecture, city, address1");
  const [system, setSystem] = useState("Order System");
  const [useLlm, setUseLlm] = useState(true);
  const [result, setResult] = useState<DesignReviewOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.designReview({ name, description, fields: fields.split(/[,\s]+/).map((f) => f.trim()).filter(Boolean), system: system || undefined, use_llm: useLlm });
      setResult(r);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader title="新規データ設計レビュー" description="新しくテーブルやデータ項目を追加したいとき、似たものが既にないかを確認し、「既存を再利用 / 既存を拡張 / 新規に作成」のどれが妥当かを提案します。" />
      <div className="grid side" style={{ gridTemplateColumns: "380px 1fr" }}>
        <div className="card">
          <div className="field"><label>追加したいデータの名前</label><input value={name} onChange={(e) => setName(e.target.value)} style={{ width: "100%" }} /></div>
          <div className="field"><label>目的・内容</label><textarea value={description} onChange={(e) => setDescription(e.target.value)} /></div>
          <div className="field"><label>持たせたい項目（カンマ区切り）</label><textarea value={fields} onChange={(e) => setFields(e.target.value)} /></div>
          <div className="field"><label>追加する側のシステム</label><input value={system} onChange={(e) => setSystem(e.target.value)} /></div>
          <div className="field"><label className="row" style={{ gap: 6 }}><input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} /> AI による解説文も生成する（設定がある場合のみ）</label></div>
          <button onClick={submit} disabled={busy || !name}>{busy ? "確認中…" : "レビューする"}</button>
          {error && <div className="alert danger" style={{ marginTop: 10 }}>{error}</div>}
        </div>
        <div>
          {!result && <div className="card muted">左のフォームに追加したいデータの内容を入力してください。</div>}
          {result && (
            <>
              <div className="card" style={{ marginBottom: 16 }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className={`rec ${result.recommendation}`} title={result.recommendation}>{REC_LABELS[result.recommendation]}</span>
                  <span className="badge info">確からしさ {Math.round(result.confidence * 100)}%</span>
                </div>
                <ul style={{ margin: "10px 0 0", paddingLeft: 18 }}>{result.rationale.map((r, i) => <li key={i}>{r}</li>)}</ul>
                {result.alternatives.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <h3>別案</h3>
                    {result.alternatives.map((a, i) => <div key={i} className="alert info" style={{ marginBottom: 6 }}><strong>{REC_LABELS[a.recommendation] ?? a.recommendation}</strong> — {a.reason}</div>)}
                  </div>
                )}
                {result.consult.length > 0 && <div style={{ marginTop: 10 }}><h3>相談先</h3>{result.consult.map((o) => <span key={o.id} style={{ marginRight: 10 }}><ObjectLink obj={o} /></span>)}</div>}
                {result.llmExplanation && (
                  <div style={{ marginTop: 12 }}>
                    <h3>AI による解説</h3>
                    <div className="alert info" style={{ whiteSpace: "pre-wrap" }}>{result.llmExplanation}</div>
                  </div>
                )}
                {!result.llmExplanation && useLlm && <div className="small muted" style={{ marginTop: 8 }}>AI 解説は生成されていません（未設定または生成失敗）。判定自体はルールに基づいて行われています。</div>}
              </div>
              <div className="card">
                <h3>似ている既存のデータ</h3>
                <table>
                  <thead><tr><th>既存データ</th><th>類似度</th><th>項目の重なり</th><th>責任チーム</th><th>関連 API</th><th>利用しているシステム</th></tr></thead>
                  <tbody>
                    {result.candidates.map((c) => (
                      <tr key={c.id}>
                        <td><ObjectLink obj={c} />{c.representedBy.length > 0 && <div className="small muted">テーブル: {c.representedBy.map((t) => t.name).join(", ")}</div>}<div className="small muted">{c.reasons.join(" · ")}</div></td>
                        <td><strong>{Math.round(c.score * 100)}%</strong></td>
                        <td><div className="chips">{c.matchedFields.map((f) => <span key={f} className="chip ok">{f}</span>)}{c.missingFields.map((f) => <span key={f} className="chip miss">+{f}</span>)}</div></td>
                        <td>{c.owners.length ? c.owners.map((o) => <div key={o.id}><ObjectLink obj={o} showType={false} /></div>) : <span className="badge warn">未設定</span>}</td>
                        <td>{c.apis.map((a) => <div key={a.id} className="small"><ObjectLink obj={a} showType={false} /></div>)}</td>
                        <td>{c.consumers.map((x) => <div key={x.id} className="small row" style={{ gap: 4 }}><TypeBadge type={x.type} /><ObjectLink obj={x} showType={false} /></div>)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
