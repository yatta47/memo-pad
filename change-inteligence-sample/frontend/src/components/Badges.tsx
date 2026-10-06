import Link from "next/link";
import { RISK_LABELS, TYPE_COLORS, TYPE_LABELS, relLabel } from "@/lib/api";
import { iconDataUri } from "@/lib/icons";
import type { ObjectRef } from "@/lib/types";

export function TypeBadge({ type }: { type: string }) {
  return (
    <span className="badge type" style={{ background: TYPE_COLORS[type] ?? "#64748b" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="icon" src={iconDataUri(type)} alt="" />
      {TYPE_LABELS[type] ?? type}
    </span>
  );
}

export function ObjectLink({ obj, showType = true }: { obj: ObjectRef; showType?: boolean }) {
  return (
    <span className="row" style={{ gap: 6, display: "inline-flex" }}>
      {showType && <TypeBadge type={obj.type} />}
      <Link href={`/objects/${encodeURIComponent(obj.id)}`}>{obj.name}</Link>
    </span>
  );
}

export function Risk({ level }: { level: string }) {
  return <span className={`badge ${level}`} title={level}>リスク {RISK_LABELS[level] ?? level}</span>;
}

export function Rel({ type }: { type: string }) {
  return <span className="rel" title={type}>{relLabel(type)}</span>;
}

export function Path({ hops }: { hops: string[] }) {
  if (!hops.length) return <span className="muted small">—</span>;
  return (
    <span className="path">
      {hops.map((h, i) => (
        <span key={i} className="row" style={{ gap: 4 }}>
          {i > 0 && <span className="arrow">→</span>}
          <span className="hop" title={h}>{relLabel(h)}</span>
        </span>
      ))}
    </span>
  );
}
