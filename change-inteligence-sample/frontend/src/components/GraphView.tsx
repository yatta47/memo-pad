"use client";

import { useEffect, useRef, useState } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { TYPE_COLORS, TYPE_LABELS, relLabel } from "@/lib/api";
import { iconDataUri } from "@/lib/icons";
import type { GraphEdge, GraphNode } from "@/lib/types";

export type LayoutMode = "layered" | "radial";

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlight?: Set<string>;
  onSelect?: (id: string | null) => void;
  onOpen?: (id: string) => void;
  defaultLayout?: LayoutMode;
  compact?: boolean;
};

// Layered layout: lanes ordered by distance from the system of record (left) to its consumers (right).
// Database -> Table -> Business Object -> API -> Service / Batch / Unknown. Teams are not part of the data flow,
// so they sit in a row underneath, each under the objects it OWNS.
const LANES: string[][] = [["Database"], ["Table"], ["BusinessObject"], ["API"], ["Service", "Batch", "Unknown"]];
const FOOTER_TYPES = ["Team"];
const LANE_GAP = 260;
const ROW_GAP = 72;
const FOOTER_GAP = 110;      // vertical space between the lowest lane row and the team row
const FOOTER_MIN_SPACING = 170; // minimum horizontal distance between teams

type Pos = { x: number; y: number };

function laneOf(type: string): number {
  const i = LANES.findIndex((lane) => lane.includes(type));
  return i === -1 ? LANES.length : i;
}

function layeredPositions(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Pos> {
  const ids = new Set(nodes.map((n) => n.id));
  const neighbours = new Map<string, string[]>();
  for (const e of edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) continue;
    neighbours.set(e.source, [...(neighbours.get(e.source) ?? []), e.target]);
    neighbours.set(e.target, [...(neighbours.get(e.target) ?? []), e.source]);
  }
  const lanes: GraphNode[][] = LANES.map(() => []);
  lanes.push([]); // unknown types
  const footer: GraphNode[] = [];
  for (const n of nodes) (FOOTER_TYPES.includes(n.type) ? footer : lanes[laneOf(n.type)]).push(n);
  // Only keep lanes that have nodes, so empty lanes do not leave gaps.
  const used = lanes.filter((l) => l.length > 0);
  used.forEach((l) => l.sort((a, b) => a.type.localeCompare(b.type) || a.name.localeCompare(b.name)));

  // Barycenter ordering (one sweep left->right, one right->left) to reduce edge crossings between lanes.
  const order = new Map<string, number>();
  const assign = () => used.forEach((l) => l.forEach((n, i) => order.set(n.id, i)));
  assign();
  const sweep = (indexes: number[]) => {
    for (const li of indexes) {
      const lane = used[li];
      const bary = new Map<string, number>();
      for (const n of lane) {
        const ns = (neighbours.get(n.id) ?? []).filter((m) => order.has(m) && laneOf(nodes.find((x) => x.id === m)!.type) !== laneOf(n.type));
        bary.set(n.id, ns.length ? ns.reduce((s, m) => s + (order.get(m) ?? 0), 0) / ns.length : order.get(n.id) ?? 0);
      }
      lane.sort((a, b) => (bary.get(a.id)! - bary.get(b.id)!) || a.name.localeCompare(b.name));
      lane.forEach((n, i) => order.set(n.id, i));
    }
  };
  sweep(used.map((_, i) => i).slice(1));
  sweep(used.map((_, i) => i).slice(0, -1).reverse());

  const positions = new Map<string, Pos>();
  const maxRows = Math.max(1, ...used.map((l) => l.length));
  used.forEach((lane, li) => {
    const offset = ((maxRows - lane.length) * ROW_GAP) / 2; // center shorter lanes vertically
    lane.forEach((n, ri) => positions.set(n.id, { x: li * LANE_GAP, y: offset + ri * ROW_GAP }));
  });
  // Team row: x = average x of the objects the team owns (or the middle), then spread out to avoid overlap.
  if (footer.length) {
    const width = Math.max(0, (used.length - 1) * LANE_GAP);
    const xs = footer.map((t) => {
      const owned = (neighbours.get(t.id) ?? []).map((m) => positions.get(m)?.x).filter((x): x is number => x != null);
      return { id: t.id, x: owned.length ? owned.reduce((a, b) => a + b, 0) / owned.length : width / 2 };
    });
    xs.sort((a, b) => a.x - b.x);
    for (let i = 1; i < xs.length; i++) xs[i].x = Math.max(xs[i].x, xs[i - 1].x + FOOTER_MIN_SPACING);
    const shift = Math.max(0, xs[xs.length - 1].x - width) / 2; // keep the row roughly centered under the lanes
    const y = (maxRows - 1) * ROW_GAP + FOOTER_GAP;
    xs.forEach((t) => positions.set(t.id, { x: t.x - shift, y }));
  }
  return positions;
}

function radialPositions(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Pos> {
  const ids = new Set(nodes.map((n) => n.id));
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) continue;
    adj.set(e.source, [...(adj.get(e.source) ?? []), e.target]);
    adj.set(e.target, [...(adj.get(e.target) ?? []), e.source]);
  }
  const hop = new Map<string, number>();
  const centers = nodes.filter((n) => n.isCenter).map((n) => n.id);
  const queue = [...centers];
  centers.forEach((c) => hop.set(c, 0));
  while (queue.length) {
    const cur = queue.shift()!;
    for (const nxt of adj.get(cur) ?? []) {
      if (!hop.has(nxt)) { hop.set(nxt, (hop.get(cur) ?? 0) + 1); queue.push(nxt); }
    }
  }
  const maxHop = Math.max(1, ...Array.from(hop.values()));
  const positions = new Map<string, Pos>();
  const byRing = new Map<number, GraphNode[]>();
  for (const n of nodes) {
    const h = hop.get(n.id) ?? maxHop + 1;
    byRing.set(h, [...(byRing.get(h) ?? []), n]);
  }
  for (const [h, ring] of byRing) {
    if (h === 0) { ring.forEach((n) => positions.set(n.id, { x: 0, y: 0 })); continue; }
    ring.sort((a, b) => a.type.localeCompare(b.type) || a.name.localeCompare(b.name));
    const radius = Math.max(h * 170, (ring.length * 90) / (2 * Math.PI));
    const step = (2 * Math.PI) / ring.length;
    const offset = -Math.PI / 2 + (h % 2 === 0 ? step / 2 : 0);
    ring.forEach((n, i) => positions.set(n.id, { x: radius * Math.cos(offset + i * step), y: radius * Math.sin(offset + i * step) }));
  }
  return positions;
}

export default function GraphView({ nodes, edges, highlight, onSelect, onOpen, defaultLayout = "layered", compact = false }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [mode, setMode] = useState<LayoutMode>(defaultLayout);

  useEffect(() => {
    if (!ref.current) return;
    const ids = new Set(nodes.map((n) => n.id));
    const positions = mode === "layered" ? layeredPositions(nodes, edges) : radialPositions(nodes, edges);
    const typeOf = new Map(nodes.map((n) => [n.id, n.type]));
    const elements: ElementDefinition[] = [
      ...nodes.map((n) => ({
        data: {
          id: n.id, label: n.name, type: n.type, color: TYPE_COLORS[n.type] ?? "#64748b", center: n.isCenter ? 1 : 0,
          icon: iconDataUri(n.type),
          unknown: n.type === "Unknown" ? 1 : 0, dim: highlight && !highlight.has(n.id) && !n.isCenter ? 1 : 0,
        },
      })),
      ...edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e) => ({
          data: {
            id: e.id, source: e.source, target: e.target, label: relLabel(e.type),
            direct: e.properties?.access_mode === "direct" ? 1 : 0,
            sameLane: mode === "layered" && laneOf(typeOf.get(e.source)!) === laneOf(typeOf.get(e.target)!) ? 1 : 0,
            footer: mode === "layered" && (FOOTER_TYPES.includes(typeOf.get(e.source)!) || FOOTER_TYPES.includes(typeOf.get(e.target)!)) ? 1 : 0,
            dim: highlight && !(highlight.has(e.source) && highlight.has(e.target)) ? 1 : 0,
          },
        })),
    ];
    const cy = cytoscape({
      container: ref.current,
      elements,
      style: [
        { selector: "node", style: { "background-color": "data(color)", label: "data(label)", color: "#1f2937", "font-size": 10, "text-valign": "bottom", "text-halign": "center", "text-margin-y": 5, width: 34, height: 34, "min-zoomed-font-size": 7, "border-width": 2, "border-color": "#fff",
            "background-image": "data(icon)", "background-fit": "contain", "background-width": "62%", "background-height": "62%", "background-clip": "none" } },
        { selector: "node[center = 1]", style: { width: 48, height: 48, "border-width": 4, "border-color": "#0f172a", "font-size": 12, "font-weight": "bold" } },
        { selector: "node[unknown = 1]", style: { shape: "diamond", "border-style": "dashed", "border-color": "#ea580c", "border-width": 3, "background-width": "50%", "background-height": "50%" } },
        { selector: "node[dim = 1]", style: { opacity: 0.25 } },
        { selector: "edge", style: { width: 1.5, "line-color": "#94a3b8", "target-arrow-color": "#94a3b8", "target-arrow-shape": "triangle", "curve-style": mode === "layered" ? "taxi" : "bezier", "taxi-direction": "horizontal", "taxi-turn": 70, "taxi-turn-min-distance": 20, label: "data(label)", "font-size": 8, "min-zoomed-font-size": 9, color: "#64748b", "text-rotation": mode === "layered" ? "none" : "autorotate", "text-opacity": mode === "layered" ? 0 : 1, "text-background-color": "#fff", "text-background-opacity": 1, "text-background-padding": "2px" } },
        { selector: "edge[footer = 1]", style: { "taxi-direction": "vertical", "taxi-turn": 45, "line-color": "#b4a7e0", "target-arrow-color": "#b4a7e0" } },
        { selector: "edge[sameLane = 1]", style: { "curve-style": "unbundled-bezier", "control-point-distances": [60], "control-point-weights": [0.5] } },
        { selector: "edge[direct = 1]", style: { "line-color": "#dc2626", "target-arrow-color": "#dc2626", "line-style": "dashed", width: 2.5, color: "#dc2626" } },
        { selector: "edge[dim = 1]", style: { opacity: 0.15 } },
        { selector: "edge.focus", style: { "text-opacity": 1, width: 2.5, "line-color": "#475569", "target-arrow-color": "#475569", "z-index": 10 } },
        { selector: "edge.focus[direct = 1]", style: { "line-color": "#dc2626", "target-arrow-color": "#dc2626" } },
        { selector: ":selected", style: { "overlay-color": "#2563eb", "overlay-opacity": 0.15, "overlay-padding": 6 } },
      ],
      layout: {
        name: "preset", animate: false, fit: true, padding: 30,
        positions: (n: cytoscape.NodeSingular) => positions.get(n.id()) ?? { x: 0, y: 0 },
      } as cytoscape.LayoutOptions,
      wheelSensitivity: 0.7,
      minZoom: 0.15,
      maxZoom: 5,
    });
    const focus = (node: cytoscape.NodeSingular | null) => {
      cy.edges().removeClass("focus");
      node?.connectedEdges().addClass("focus");
    };
    cy.on("tap", "node", (ev) => { focus(ev.target); onSelect?.(ev.target.id()); });
    cy.on("tap", (ev) => { if (ev.target === cy) { focus(null); onSelect?.(null); } });
    cy.on("mouseover", "node", (ev) => { if (cy.$("node:selected").empty()) focus(ev.target); });
    cy.on("mouseout", "node", () => { if (cy.$("node:selected").empty()) focus(null); });
    cy.on("dbltap", "node", (ev) => onOpen?.(ev.target.id()));
    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [nodes, edges, highlight, onSelect, onOpen, mode]);

  const zoomBy = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    const w = cy.width(), h = cy.height();
    cy.animate({ zoom: { level: cy.zoom() * factor, renderedPosition: { x: w / 2, y: h / 2 } }, duration: 120 });
  };
  const fit = () => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 30 }, duration: 160 });

  const present = Array.from(new Set(nodes.map((n) => n.type)));
  const lanesPresent = LANES.map((l) => l.filter((t) => present.includes(t))).filter((l) => l.length > 0);
  return (
    <div className={`graph${compact ? " compact" : ""}`}>
      <div ref={ref} style={{ position: "absolute", inset: 0 }} />
      <div className="controls">
        <div className="segmented">
          <button type="button" className={mode === "layered" ? "on" : ""} onClick={() => setMode("layered")} title="元データ（左）から利用側（右）へ階層で並べる">階層表示</button>
          <button type="button" className={mode === "radial" ? "on" : ""} onClick={() => setMode("radial")} title="選んだ対象を中心に、関係の近い順に同心円で並べる">放射表示</button>
        </div>
        <button type="button" className="secondary" onClick={() => zoomBy(1.4)} title="拡大">＋</button>
        <button type="button" className="secondary" onClick={() => zoomBy(1 / 1.4)} title="縮小">－</button>
        <button type="button" className="secondary" onClick={fit} title="全体を表示">全体</button>
      </div>
      {mode === "layered" && lanesPresent.length > 1 && (
        <div className="lanes">
          <span className="muted">元データ</span>
          {lanesPresent.map((l, i) => (
            <span key={i} className="row" style={{ gap: 4 }}>
              {i > 0 && <span className="muted">→</span>}
              <span className="lane">{l.map((t) => TYPE_LABELS[t] ?? t).join(" / ")}</span>
            </span>
          ))}
          <span className="muted">→ 利用側</span>
          {present.includes("Team") && <span className="muted">· 担当チームは下段</span>}
        </div>
      )}
      <div className="legend">
        {present.map((t) => (
          // eslint-disable-next-line @next/next/no-img-element
          <span key={t}><img className="icon" src={iconDataUri(t, { shape: t === "Unknown" ? "diamond" : "circle" })} alt="" />{TYPE_LABELS[t] ?? t}</span>
        ))}
        <span><span className="dot" style={{ background: "#dc2626" }} />正規ルート外のデータ参照</span>
      </div>
    </div>
  );
}
