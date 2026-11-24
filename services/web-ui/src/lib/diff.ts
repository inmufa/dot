export type DiffKind = "add" | "del" | "ctx" | "hunk" | "meta";
export interface DiffLine {
  kind: DiffKind;
  text: string;
  oldNo: number | null;
  newNo: number | null;
}
export interface ParsedDiff {
  lines: DiffLine[];
  added: number;
  removed: number;
}

const HUNK = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;

/** Parse a unified diff or the backend's simple "- old / + new" Edit format. */
export function parseDiff(raw: string): ParsedDiff {
  const src = raw.replace(/\r\n/g, "\n").replace(/\n$/, "").split("\n");
  const unified = src.some((l) => HUNK.test(l));
  const lines: DiffLine[] = [];
  let added = 0;
  let removed = 0;
  let o = 0;
  let n = 0;
  let inHunk = false;
  for (const l of src) {
    const h = HUNK.exec(l);
    if (h) {
      o = Number(h[1]);
      n = Number(h[2]);
      inHunk = true;
      lines.push({ kind: "hunk", text: l, oldNo: null, newNo: null });
    } else if (unified && !inHunk) {
      lines.push({ kind: "meta", text: l, oldNo: null, newNo: null });
    } else if (l.startsWith("+")) {
      added++;
      lines.push({ kind: "add", text: l.slice(1), oldNo: null, newNo: unified ? n++ : null });
    } else if (l.startsWith("-")) {
      removed++;
      lines.push({ kind: "del", text: l.slice(1), oldNo: unified ? o++ : null, newNo: null });
    } else if (l.startsWith("\\")) {
      lines.push({ kind: "meta", text: l, oldNo: null, newNo: null });
    } else {
      const text = unified && l.startsWith(" ") ? l.slice(1) : l;
      lines.push({ kind: "ctx", text, oldNo: unified ? o++ : null, newNo: unified ? n++ : null });
    }
  }
  return { lines, added, removed };
}
