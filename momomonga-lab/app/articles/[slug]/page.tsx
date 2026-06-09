import { notFound } from "next/navigation";
import { getArticle } from "@/lib/content/articles";
import { getProduct } from "@/lib/content/products";
import { getState } from "@/lib/content/states";

type Props = {
  params: Promise<{ slug: string }>;
};

export default async function ArticleDetailPage({ params }: Props) {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article) notFound();

  const relatedStates = article.stateSlugs.map(getState).filter(Boolean);
  const relatedProducts = article.productSlugs.map(getProduct).filter(Boolean);

  return (
    <main className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <article className="card">
        <p className="eyebrow">{article.publishedAt}</p>
        <h1 className="mt-4 text-4xl leading-tight font-semibold">{article.title}</h1>
        <p className="mt-5 text-base leading-8 text-[var(--muted)]">{article.description}</p>
        <div className="mt-8 space-y-5 text-[15px] leading-8 whitespace-pre-wrap">
          {article.body}
        </div>
      </article>
      <aside className="space-y-6">
        <section className="card">
          <p className="eyebrow">States</p>
          <ul className="mt-4 space-y-3 text-sm text-[var(--muted)]">
            {relatedStates.map((state) => (
              <li key={state.slug}>{state.title}</li>
            ))}
          </ul>
        </section>
        <section className="card">
          <p className="eyebrow">Products</p>
          <ul className="mt-4 space-y-4 text-sm text-[var(--muted)]">
            {relatedProducts.map((product) => (
              <li key={product.slug}>
                <p className="font-semibold text-[var(--text)]">{product.name}</p>
                <p className="mt-1 leading-6">{product.summary}</p>
              </li>
            ))}
          </ul>
        </section>
      </aside>
    </main>
  );
}
