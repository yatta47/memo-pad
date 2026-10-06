import { OBS_LABELS, SOURCE_LABELS } from "@/lib/api";
import type { EvidenceOut } from "@/lib/types";

const fmt = (v?: string | null) => (v ? v.replace("T", " ").slice(0, 16) : "—");

export default function EvidenceList({ items }: { items: EvidenceOut[] }) {
  if (!items.length) return <span className="muted small">根拠なし</span>;
  return (
    <div>
      {items.map((e) => (
        <div key={e.id} className="evidence">
          <div className="row" style={{ gap: 6 }}>
            <span className="badge outline" title={e.source_type ?? ""}>{SOURCE_LABELS[e.source_type ?? ""] ?? e.source_type ?? "不明"}</span>
            <span className="badge outline" title={e.observation_type ?? ""}>{OBS_LABELS[e.observation_type ?? ""] ?? e.observation_type ?? "—"}</span>
            {e.confidence != null && <span className="badge info">確からしさ {Math.round(e.confidence * 100)}%</span>}
            {e.resolved_from && <span className="badge warn">{e.resolved_from} から引き継ぎ</span>}
          </div>
          <div style={{ marginTop: 4 }}><code>{e.source_ref}</code></div>
          <div className="muted" style={{ marginTop: 2 }}>
            初回観測 {fmt(e.first_seen)} · 最終観測 {fmt(e.last_seen)}
          </div>
        </div>
      ))}
    </div>
  );
}
