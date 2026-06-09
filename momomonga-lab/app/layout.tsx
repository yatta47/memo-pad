import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "momomonga lab",
  description: "レビューをもとに、暮らしのなりたい状態を組み立てる。"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>
        <div className="shell">
          <header className="mb-10 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <Link href="/" className="text-3xl font-semibold tracking-[0.08em]">
                momomonga lab
              </Link>
              <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--muted)]">
                暮らしの&quot;なりたい状態&quot;を、実レビューから組み立てる。
              </p>
            </div>
            <nav className="flex gap-5 text-sm text-[var(--muted)]">
              <Link href="/articles">Articles</Link>
              <Link href="/states">States</Link>
              <Link href="/products">Products</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
