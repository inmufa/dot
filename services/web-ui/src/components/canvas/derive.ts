import type { FileEntry } from "@/lib/api/types";
import type { Item } from "@/lib/stream/reducer";

export type FileKind = FileEntry["kind"];

const EXT: Record<string, FileKind> = {
  html: "html", htm: "html", md: "md", markdown: "md", png: "image", jpg: "image", jpeg: "image", gif: "image", webp: "image", svg: "image",
  csv: "csv", tsv: "csv",
};
const CODE = new Set(["py", "ts", "tsx", "js", "jsx", "json", "yaml", "yml", "toml", "css", "sh", "rs", "go", "sql", "txt", "log", "ini"]);

export const extOf = (path: string): string => (/\.([A-Za-z0-9]+)$/.exec(path)?.[1] ?? "").toLowerCase();
export function previewKind(path: string): FileKind {
  const e = extOf(path);
  return EXT[e] ?? (CODE.has(e) ? "code" : "other");
}

const WRITERS = new Set(["Write", "Edit", "MultiEdit", "NotebookEdit"]);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

/** Files the agent wrote or edited, newest last, deduplicated by path. */
export function writtenFiles(items: Item[]): { path: string; kind: FileKind }[] {
  const seen = new Map<string, FileKind>();
  for (const it of items) {
    if (it.kind !== "tool" || !WRITERS.has(it.name) || it.status !== "done") continue;
    const p = str(it.args.file_path) ?? str(it.args.path);
    if (!p) continue;
    seen.delete(p);
    seen.set(p, previewKind(p));
  }
  return [...seen].map(([path, kind]) => ({ path, kind }));
}

export const hostOf = (url: string): string => {
  try {
    return new URL(url).host;
  } catch {
    return url.slice(0, 40);
  }
};

export interface TreeNode {
  name: string;
  path: string;
  file: FileEntry | null;
  children: TreeNode[];
}
export function buildTree(files: FileEntry[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", file: null, children: [] };
  for (const f of files) {
    let cur = root;
    const parts = f.path.split("/").filter(Boolean);
    parts.forEach((name, i) => {
      const path = parts.slice(0, i + 1).join("/");
      let next = cur.children.find((c) => c.path === path);
      if (!next) {
        next = { name, path, file: null, children: [] };
        cur.children.push(next);
      }
      if (i === parts.length - 1) next.file = f;
      cur = next;
    });
  }
  const sort = (n: TreeNode) => {
    n.children.sort((a, b) => Number(!!a.file) - Number(!!b.file) || a.name.localeCompare(b.name));
    n.children.forEach(sort);
  };
  sort(root);
  return root.children;
}

/** Minimal RFC 4180 parser with a row cap. */
export function parseCsv(text: string, delim = ",", maxRows = 500): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let q = false;
  for (let i = 0; i < text.length && rows.length <= maxRows; i++) {
    const c = text.charAt(i);
    if (q) {
      if (c === '"' && text.charAt(i + 1) === '"') { cell += '"'; i++; }
      else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === delim) { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text.charAt(i + 1) === "\n") i++;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows.slice(0, maxRows + 1);
}

export const fmtSize = (n: number): string => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} kB` : `${(n / 1048576).toFixed(1)} MB`);
