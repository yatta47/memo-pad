import { CalendarClock, CircleQuestionMark, CodeXml, Database, Server, Table2, Tag, Users, type IconNode } from "lucide";
import { TYPE_COLORS } from "./api";

// Icons come from Lucide (https://lucide.dev, ISC license). The core package exposes each icon as data
// ([tag, attributes][]), so the same glyph can be rendered as an inline SVG string for Cytoscape node
// backgrounds, legends and type badges without a React or image dependency.
const ICONS: Record<string, IconNode> = {
  Team: Users,
  Service: Server,
  API: CodeXml,
  BusinessObject: Tag,
  Database: Database,
  Table: Table2,
  Batch: CalendarClock,
  Unknown: CircleQuestionMark,
};

function glyph(node: IconNode): string {
  return node
    .map(([tag, attrs]) => `<${tag} ${Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(" ")}/>`)
    .join("");
}

export function iconSvg(type: string, opts?: { background?: string; shape?: "circle" | "diamond" | "none"; size?: number }): string {
  const node = ICONS[type] ?? CircleQuestionMark;
  const bg = opts?.background ?? TYPE_COLORS[type] ?? "#64748b";
  const shape = opts?.shape ?? "none";
  const backdrop =
    shape === "circle" ? `<circle cx="12" cy="12" r="12" fill="${bg}"/>` :
    shape === "diamond" ? `<path d="M12 0L24 12 12 24 0 12z" fill="${bg}"/>` : "";
  const scale = shape === "none" ? "" : 'transform="translate(5 5) scale(0.58)"';
  const size = opts?.size ?? 24;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}">${backdrop}<g ${scale} fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${glyph(node)}</g></svg>`;
}

export function iconDataUri(type: string, opts?: Parameters<typeof iconSvg>[1]): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(iconSvg(type, opts))}`;
}
