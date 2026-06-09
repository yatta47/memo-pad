import Link from "next/link";
import { getArticles } from "@/lib/content/articles";

export default function ArticlesPage() {
  const articles = getArticles();

  return (
    <main className="space-y-6">
      <h1 className="text-4xl font-semibold">Articles</h1>
      <div className="grid gap-5">
        {articles.map((article) => (
          <Link key={article.slug} href={`/articles/${article.slug}`} className="card block">
            <p className="eyebrow">{article.publishedAt}</p>
            <h2 className="mt-3 text-2xl font-semibold">{article.title}</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--muted)]">{article.description}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
