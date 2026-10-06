"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ObjectLink, Rel, TypeBadge } from "@/components/Badges";
import EvidenceList from "@/components/Evidence";
import { api, STATUS_LABELS, TYPE_LABELS, propLabel, propValue } from "@/lib/api";
import type { ObjectRef, ResolveOut, UnknownDetail } from "@/lib/types";

export default function UnknownDetailPage() {
  const { id } = useParams<{ id: string }>();
  const unknownId = decodeURIComponent(id);
  const router = useRouter();
  const [u, setU] = useState<UnknownDetail | null>(null);
  const [teams, setTeams] = useState<ObjectRef[]>([]);
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [targetId, setTargetId] = useState("");
  const [newType, setNewType] = useState<"Service" | "Batch">("Batch");
  const [newName, setNewName] = useState("");
  const [newSystem, setNewSystem] = useState("");
  const [teamId, setTeamId] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<ResolveOut | null>(null);

  useEffect(() => {
    api.unknown(unknownId).then((d) => { setU(d); if (d.candidates[0]) setTargetId(d.candidates[0].id); }).catch((e) => setError(e.message));
    api.objects({ type: ["Team"] }).then(setTeams).catch(() => {});
  }, [unknownId]);

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const body = mode === "existing"
        ? { target_id: targetId, note: note || undefined }
        : { new_object: { type: newType, name: newName, system: newSystem || undefined, team_id: teamId || undefined }, note: note || undefined };
      const res = await api.resolve(unknownId, body);
      setDone(res);
      setU(await api.unknown(unknownId));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  if (error && !u) return <div className="alert danger">{error}</div>;
  if (!u) return <div className="muted">読み込み中…</div>;
  const resolved = u.status === "resolved";

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="row"><TypeBadge type="Unknown" /><h1>{u.name}</h1><span className={`badge ${resolved ? "LOW" : "HIGH"}`}>{STATUS_LABELS[u.status] ?? u.status}</span></div>
          <p className="lead">{u.hint}</p>
        </div>
      </div>
      {done && (
        <div className="alert ok">
          <strong>{done.resolvedTo.name}</strong> として特定しました。関係 {done.movedRelations} 件を付け替え、根拠 {done.inheritedEvidence} 件を引き継ぎました。
          {" "}<Link href={`/map?center=${encodeURIComponent(done.resolvedTo.id)}`}>→ 全体マップで見る</Link>{" · "}<Link href="/unknowns">→ 一覧へ戻る</Link>
        </div>
      )}
      <div className="grid cols-2">
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>根拠（{u.evidence.length}）</h3>
            <EvidenceList items={u.evidence} />
          </div>
          <div className="card">
            <h3>観測された関係（{u.relations.length}）</h3>
            {resolved && <div className="muted small" style={{ marginBottom: 6 }}>関係は <code>{u.resolvedTo}</code> に付け替え済みです。この未特定は履歴として残しています。</div>}
            <table>
              <thead><tr><th>関係</th><th>相手</th><th>補足</th></tr></thead>
              <tbody>
                {u.relations.map((r) => (
                  <tr key={r.id}>
                    <td><Rel type={r.type} /> {r.direction === "out" ? "→" : "←"}</td>
                    <td><ObjectLink obj={r.direction === "out" ? r.target : r.source} /></td>
                    <td className="small muted">{Object.entries(r.properties).map(([k, v]) => `${propLabel(k)}: ${propValue(k, v)}`).join(" / ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <h3>正体を特定する</h3>
          {resolved ? (
            <div className="alert info">特定済み: <ObjectLink obj={{ id: u.resolvedTo ?? "", type: "Batch", name: u.resolvedTo ?? "" }} showType={false} /></div>
          ) : (
            <>
              <div className="toolbar">
                <button className={mode === "existing" ? "" : "secondary"} onClick={() => setMode("existing")}>登録済みのものから選ぶ</button>
                <button className={mode === "new" ? "" : "secondary"} onClick={() => setMode("new")}>新しく登録する</button>
              </div>
              {mode === "existing" ? (
                <div className="field">
                  <label>候補（根拠との一致度が高い順）</label>
                  <select value={targetId} onChange={(e) => setTargetId(e.target.value)} style={{ width: "100%" }}>
                    {u.candidates.map((c) => <option key={c.id} value={c.id}>{TYPE_LABELS[c.type] ?? c.type}: {c.name}</option>)}
                  </select>
                </div>
              ) : (
                <>
                  <div className="field"><label>種類</label>
                    <select value={newType} onChange={(e) => setNewType(e.target.value as "Service" | "Batch")}><option value="Batch">バッチ処理</option><option value="Service">サービス</option></select></div>
                  <div className="field"><label>名称</label><input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="例: 旧レポート抽出バッチ" style={{ width: "100%" }} /></div>
                  <div className="field"><label>所属システム</label><input value={newSystem} onChange={(e) => setNewSystem(e.target.value)} placeholder="例: 分析" /></div>
                  <div className="field"><label>責任チーム（任意）</label>
                    <select value={teamId} onChange={(e) => setTeamId(e.target.value)}><option value="">— 未設定 —</option>{teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
                </>
              )}
              <div className="field"><label>メモ（記録用）</label><textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="なぜこの特定が正しいと判断したか" /></div>
              {error && <div className="alert danger">{error}</div>}
              <button onClick={submit} disabled={busy || (mode === "existing" ? !targetId : !newName)}>{busy ? "処理中…" : "この内容で特定する"}</button>
              <button className="secondary" style={{ marginLeft: 8 }} onClick={() => router.push("/unknowns")}>戻る</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
