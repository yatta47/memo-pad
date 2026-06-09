import fs from "node:fs";
import path from "node:path";

export function readDir(dir: string) {
  return fs.readdirSync(dir, { withFileTypes: true }).filter((entry) => entry.isFile());
}

export function readText(filePath: string) {
  return fs.readFileSync(filePath, "utf8");
}

export function contentPath(...segments: string[]) {
  return path.join(process.cwd(), "content", ...segments);
}
