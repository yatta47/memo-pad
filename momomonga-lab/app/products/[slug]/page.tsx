import { notFound } from "next/navigation";
import { getProduct } from "@/lib/content/products";

type Props = {
  params: Promise<{ slug: string }>;
};

export default async function ProductDetailPage({ params }: Props) {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) notFound();

  return (
    <main className="card">
      <p className="eyebrow">{product.category}</p>
      <h1 className="mt-4 text-4xl font-semibold">{product.name}</h1>
      <p className="mt-5 text-base leading-8 text-[var(--muted)]">{product.summary}</p>
      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <section>
          <h2 className="text-lg font-semibold">向いている人</h2>
          <ul className="mt-3 space-y-2 text-sm leading-7 text-[var(--muted)]">
            {product.goodFor.map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="text-lg font-semibold">向いていない人</h2>
          <ul className="mt-3 space-y-2 text-sm leading-7 text-[var(--muted)]">
            {product.notFor.map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}
