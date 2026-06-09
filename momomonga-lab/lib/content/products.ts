import { contentPath, readDir, readText } from "@/lib/content/files";

export type Product = {
  slug: string;
  name: string;
  category: string;
  summary: string;
  goodFor: string[];
  notFor: string[];
};

export function getProducts(): Product[] {
  const dir = contentPath("products");
  return readDir(dir).map((entry) => JSON.parse(readText(`${dir}/${entry.name}`)) as Product);
}

export function getProduct(slug: string) {
  return getProducts().find((product) => product.slug === slug);
}
