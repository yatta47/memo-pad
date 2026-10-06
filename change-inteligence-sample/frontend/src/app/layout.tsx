import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Change Intelligence — システム依存関係マップ",
  description: "変更影響分析・未特定の利用元の特定・新規データ設計レビュー",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <div className="shell">
          <Sidebar />
          <div className="content">
            <main>{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
