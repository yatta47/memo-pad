import { contentPath, readDir, readText } from "@/lib/content/files";

export type State = {
  slug: string;
  title: string;
  symptoms: string[];
  goal: string;
};

export function getStates(): State[] {
  const dir = contentPath("states");
  return readDir(dir).map((entry) => JSON.parse(readText(`${dir}/${entry.name}`)) as State);
}

export function getState(slug: string) {
  return getStates().find((state) => state.slug === slug);
}
