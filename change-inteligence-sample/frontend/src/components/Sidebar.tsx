"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { CircleQuestionMark, ClipboardCheck, GitBranch, LayoutDashboard, ShieldAlert, Waypoints } from "lucide";
import Icon from "@/components/Icon";
import { api } from "@/lib/api";

export const NAV = [
  { href: "/", label: "ダッシュボード", icon: LayoutDashboard, match: (p: string) => p === "/" },
  { href: "/map", label: "全体マップ", icon: Waypoints, match: (p: string) => p.startsWith("/map") || p.startsWith("/objects") },
  { href: "/impact", label: "変更影響分析", icon: GitBranch, match: (p: string) => p.startsWith("/impact") },
  { href: "/unknowns", label: "未特定の利用元", icon: CircleQuestionMark, match: (p: string) => p.startsWith("/unknowns") },
  { href: "/governance", label: "ルール逸脱の確認", icon: ShieldAlert, match: (p: string) => p.startsWith("/governance") },
  { href: "/design-review", label: "新規データ設計レビュー", icon: ClipboardCheck, match: (p: string) => p.startsWith("/design-review") },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [unknownOpen, setUnknownOpen] = useState<number | null>(null);
  useEffect(() => {
    api.governance().then((s) => setUnknownOpen(s.unknownOpen)).catch(() => setUnknownOpen(null));
  }, [pathname]);
  return (
    <aside className="sidebar">
      <Link href="/" className="brand" style={{ textDecoration: "none" }}>
        <span className="logo"><Icon node={Waypoints} size={16} /></span>
        <span>Change Intelligence<small>システム依存関係マップ</small></span>
      </Link>
      <div className="section">メニュー</div>
      <nav>
        {NAV.map((l) => (
          <Link key={l.href} href={l.href} className={l.match(pathname) ? "active" : ""}>
            <Icon node={l.icon} className="ico" />
            <span>{l.label}</span>
            {l.href === "/unknowns" && unknownOpen ? <span className="badge count">{unknownOpen}</span> : null}
          </Link>
        ))}
      </nav>
      <div className="foot">PoC 環境 · データは fixture から投入</div>
    </aside>
  );
}
