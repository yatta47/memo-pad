import { SectionCard } from "@/components/section-card";
import { getArticles } from "@/lib/content/articles";
import { getProducts } from "@/lib/content/products";
import { getStates } from "@/lib/content/states";

export default function HomePage() {
  const latestArticle = getArticles()[0];
  const states = getStates();
  const products = getProducts();

  return (
    <main className="space-y-10">
      <section className="card overflow-hidden">
        <div className="grid gap-8 md:grid-cols-[1.2fr_0.8fr]">
          <div>
            <p className="eyebrow">State-Driven Review Media</p>
            <h1 className="mt-4 max-w-3xl text-5xl leading-tight font-semibold">
              商品ではなく、暮らしの状態から選べるメディアをつくる。
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-[var(--muted)]">
              momomonga lab は、Amazon商品と実レビューをもとに、
              「どんな状態をつくりたいか」から道具を選べるようにする実験室です。
            </p>
          </div>
          <div className="rounded-[20px] border border-[var(--line)] bg-[#f2e4d6] p-6">
            <p className="eyebrow">Latest Article</p>
            <h2 className="mt-4 text-2xl font-semibold">{latestArticle.title}</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--muted)]">
              {latestArticle.description}
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        <SectionCard
          href="/articles"
          eyebrow="Articles"
          title="記事"
          description="状態別レビュー記事の一覧。悩みと理想状態から導線を作る。"
        />
        <SectionCard
          href="/states"
          eyebrow="States"
          title="状態"
          description={`現在 ${states.length} 件。空気、集中、睡眠など目指す状態を軸に整理する。`}
        />
        <SectionCard
          href="/products"
          eyebrow="Products"
          title="商品"
          description={`現在 ${products.length} 件。レビューの要約と、向く人/向かない人を持つ。`}
        />
      </section>
    </main>
  );
}
