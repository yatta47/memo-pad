import matter from "gray-matter";
import { contentPath, readDir, readText } from "@/lib/content/files";

export type Article = {
  slug: string;
  title: string;
  description: string;
  publishedAt: string;
  stateSlugs: string[];
  productSlugs: string[];
  body: string;
};

export function getArticles(): Article[] {
  const dir = contentPath("articles");
  return readDir(dir)
    .map((entry) => {
      const source = readText(`${dir}/${entry.name}`);
      const { data, content } = matter(source);
      return {
        slug: entry.name.replace(/\.mdx$/, ""),
        title: data.title,
        description: data.description,
        publishedAt: data.publishedAt,
        stateSlugs: data.stateSlugs ?? [],
        productSlugs: data.productSlugs ?? [],
        body: content.trim()
      } satisfies Article;
    })
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
}

export function getArticle(slug: string) {
  return getArticles().find((article) => article.slug === slug);
}
