import { getArticle } from "@/lib/content/articles";

const slug = process.argv[2] ?? "air-at-home-for-remote-work";
const article = getArticle(slug);

if (!article) {
  console.error(`Article not found: ${slug}`);
  process.exit(1);
}

const slides = [
  article.title,
  article.description,
  "目指す状態を1枚で言う",
  "最初の1台を示す",
  "最後にブログ記事へ送る"
];

console.log(JSON.stringify({ slug, slides }, null, 2));
