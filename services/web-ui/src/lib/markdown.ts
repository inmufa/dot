// Small, safe markdown subset parser (no HTML passthrough). Output is rendered by React elements.
export type Inline =
  | { t: "text"; v: string }
  | { t: "code"; v: string }
  | { t: "strong" | "em" | "del"; c: Inline[] }
  | { t: "link"; href: string; c: Inline[] };

export type Block =
  | { t: "p"; c: Inline[] }
  | { t: "h"; level: number; c: Inline[] }
  | { t: "code"; lang: string; v: string; closed: boolean }
  | { t: "quote"; c: Block[] }
  | { t: "list"; ordered: boolean; start: number; items: Block[][] }
  | { t: "table"; head: Inline[][]; rows: Inline[][][]; align: ("left" | "right" | "center" | null)[] }
  | { t: "hr" };

const SAFE_URL = /^(https?:\/\/|mailto:)/i;

export function parseInline(src: string): Inline[] {
  // Guard against quadratic scans on pathological input.
  if (src.length > 4000) return [{ t: "text", v: src }];
  const out: Inline[] = [];
  let text = "";
  const flush = () => {
    if (text) out.push({ t: "text", v: text });
    text = "";
  };
  let i = 0;
  while (i < src.length) {
    const rest = src.slice(i);
    let m: RegExpExecArray | null;
    if (rest.startsWith("\\") && rest.length > 1 && /[\\`*_[\]()~#>-]/.test(rest[1] ?? "")) {
      text += rest[1] ?? "";
      i += 2;
    } else if ((m = /^(`+)([\s\S]*?[^`])\1(?!`)/.exec(rest))) {
      flush();
      out.push({ t: "code", v: (m[2] ?? "").replace(/^ (.*) $/, "$1") });
      i += m[0].length;
    } else if ((m = /^\*\*(?=\S)([\s\S]+?)(?<=\S)\*\*/.exec(rest)) ?? (m = /^__(?=\S)([\s\S]+?)(?<=\S)__/.exec(rest))) {
      flush();
      out.push({ t: "strong", c: parseInline(m[1] ?? "") });
      i += m[0].length;
    } else if ((m = /^~~(?=\S)([\s\S]+?)(?<=\S)~~/.exec(rest))) {
      flush();
      out.push({ t: "del", c: parseInline(m[1] ?? "") });
      i += m[0].length;
    } else if ((m = /^\*(?=[^\s*])([^*]+?)(?<=\S)\*/.exec(rest)) ?? (m = /^_(?=[^\s_])([^_]+?)(?<=\S)_(?![A-Za-z0-9])/.exec(rest))) {
      flush();
      out.push({ t: "em", c: parseInline(m[1] ?? "") });
      i += m[0].length;
    } else if ((m = /^\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/.exec(rest))) {
      flush();
      const href = m[2] ?? "";
      if (SAFE_URL.test(href)) out.push({ t: "link", href, c: parseInline(m[1] ?? "") });
      else out.push({ t: "text", v: m[1] ?? "" });
      i += m[0].length;
    } else if ((m = /^https?:\/\/[^\s<>)\]]+[^\s<>)\].,;:!?'"]/.exec(rest))) {
      flush();
      out.push({ t: "link", href: m[0], c: [{ t: "text", v: m[0] }] });
      i += m[0].length;
    } else {
      text += src[i] ?? "";
      i++;
    }
  }
  flush();
  return out;
}

const FENCE = /^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)[^`]*$/;
const LIST = /^( *)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$/;

function cells(line: string): string[] {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

function startsBlock(l: string, next: string | undefined): boolean {
  return (
    FENCE.test(l) || /^ {0,3}#{1,6}\s/.test(l) || /^ {0,3}>/.test(l) || LIST.test(l) ||
    /^ {0,3}([-*_])( *\1){2,} *$/.test(l) || (l.includes("|") && next !== undefined && TABLE_SEP.test(next))
  );
}

export function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i] ?? "";
    if (!l.trim()) {
      i++;
      continue;
    }
    const f = FENCE.exec(l);
    if (f) {
      const fence = f[1] ?? "```";
      const body: string[] = [];
      i++;
      let closed = false;
      while (i < lines.length) {
        const cur = lines[i] ?? "";
        if (new RegExp(`^ {0,3}${fence[0] === "`" ? "`" : "~"}{${fence.length},}\\s*$`).test(cur)) {
          closed = true;
          i++;
          break;
        }
        body.push(cur);
        i++;
      }
      blocks.push({ t: "code", lang: f[2] ?? "", v: body.join("\n"), closed });
      continue;
    }
    const h = /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/.exec(l);
    if (h) {
      blocks.push({ t: "h", level: (h[1] ?? "#").length, c: parseInline(h[2] ?? "") });
      i++;
      continue;
    }
    if (/^ {0,3}([-*_])( *\1){2,} *$/.test(l)) {
      blocks.push({ t: "hr" });
      i++;
      continue;
    }
    if (/^ {0,3}>/.test(l)) {
      const q: string[] = [];
      while (i < lines.length && /^ {0,3}>/.test(lines[i] ?? "")) {
        q.push((lines[i] ?? "").replace(/^ {0,3}> ?/, ""));
        i++;
      }
      blocks.push({ t: "quote", c: parseBlocks(q.join("\n")) });
      continue;
    }
    const lm = LIST.exec(l);
    if (lm) {
      const ordered = /\d/.test(lm[2] ?? "");
      const base = (lm[1] ?? "").length;
      const items: Block[][] = [];
      const start = ordered ? parseInt(lm[2] ?? "1", 10) : 1;
      while (i < lines.length) {
        const m = LIST.exec(lines[i] ?? "");
        if (!m || (m[1] ?? "").length !== base) break;
        const body = [m[3] ?? ""];
        i++;
        while (i < lines.length) {
          const cur = lines[i] ?? "";
          if (!cur.trim()) {
            if (/^ {2,}\S/.test(lines[i + 1] ?? "")) {
              body.push("");
              i++;
              continue;
            }
            break;
          }
          const cm = LIST.exec(cur);
          if (cm && (cm[1] ?? "").length <= base) break;
          if (!/^ {2,}/.test(cur) && startsBlock(cur, lines[i + 1])) break;
          body.push(cur.replace(new RegExp(`^ {0,${base + 2}}`), ""));
          i++;
        }
        items.push(parseBlocks(body.join("\n")));
      }
      blocks.push({ t: "list", ordered, start, items });
      continue;
    }
    if (l.includes("|") && TABLE_SEP.test(lines[i + 1] ?? "")) {
      const head = cells(l).map(parseInline);
      const align = cells(lines[i + 1] ?? "").map((c) =>
        c.startsWith(":") && c.endsWith(":") ? ("center" as const) : c.endsWith(":") ? ("right" as const) : c.startsWith(":") ? ("left" as const) : null,
      );
      i += 2;
      const rows: Inline[][][] = [];
      while (i < lines.length && (lines[i] ?? "").trim() && (lines[i] ?? "").includes("|")) {
        rows.push(cells(lines[i] ?? "").map(parseInline));
        i++;
      }
      blocks.push({ t: "table", head, rows, align });
      continue;
    }
    const para: string[] = [l];
    i++;
    while (i < lines.length && (lines[i] ?? "").trim() && !startsBlock(lines[i] ?? "", lines[i + 1])) {
      para.push(lines[i] ?? "");
      i++;
    }
    blocks.push({ t: "p", c: parseInline(para.join("\n")) });
  }
  return blocks;
}
