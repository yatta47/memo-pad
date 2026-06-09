import Link from "next/link";
import { getProducts } from "@/lib/content/products";

export default function ProductsPage() {
  const products = getProducts();

  return (
    <main className="space-y-6">
      <h1 className="text-4xl font-semibold">Products</h1>
      <div className="grid gap-5 md:grid-cols-2">
        {products.map((product) => (
          <Link key={product.slug} href={`/products/${product.slug}`} className="card block">
            <p className="eyebrow">{product.category}</p>
            <h2 className="mt-3 text-2xl font-semibold">{product.name}</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--muted)]">{product.summary}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
