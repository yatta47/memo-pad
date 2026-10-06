import type { IconNode } from "lucide";
import { createElement } from "react";

// Renders a Lucide IconNode ([tag, attrs][]) as an inline React SVG.
export default function Icon({ node, size = 18, className, strokeWidth = 2 }: { node: IconNode; size?: number; className?: string; strokeWidth?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {node.map(([tag, attrs], i) => createElement(tag, { key: i, ...attrs }))}
    </svg>
  );
}
