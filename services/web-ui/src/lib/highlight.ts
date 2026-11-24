// Lazy shiki: this module is only imported (dynamically) when the first code block settles.
import { createCssVariablesTheme, createHighlighterCore, type HighlighterCore } from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";

const LOADERS: Record<string, () => Promise<unknown>> = {
  ts: () => import("shiki/langs/typescript.mjs"),
  tsx: () => import("shiki/langs/tsx.mjs"),
  js: () => import("shiki/langs/javascript.mjs"),
  jsx: () => import("shiki/langs/jsx.mjs"),
  python: () => import("shiki/langs/python.mjs"),
  bash: () => import("shiki/langs/bash.mjs"),
  json: () => import("shiki/langs/json.mjs"),
  diff: () => import("shiki/langs/diff.mjs"),
  css: () => import("shiki/langs/css.mjs"),
  html: () => import("shiki/langs/html.mjs"),
  markdown: () => import("shiki/langs/markdown.mjs"),
  yaml: () => import("shiki/langs/yaml.mjs"),
  toml: () => import("shiki/langs/toml.mjs"),
  sql: () => import("shiki/langs/sql.mjs"),
  rust: () => import("shiki/langs/rust.mjs"),
  go: () => import("shiki/langs/go.mjs"),
  dockerfile: () => import("shiki/langs/dockerfile.mjs"),
};

const ALIAS: Record<string, string> = {
  typescript: "ts", javascript: "js", py: "python", sh: "bash", shell: "bash", zsh: "bash",
  console: "bash", yml: "yaml", md: "markdown", rs: "rust", golang: "go", patch: "diff", jsonc: "json",
};

export function normalizeLang(lang: string): string | null {
  const l = lang.toLowerCase().trim();
  const key = ALIAS[l] ?? l;
  return key in LOADERS ? key : null;
}

const theme = createCssVariablesTheme({ name: "dot", variablePrefix: "--sh-", variableDefaults: {}, fontStyle: true });
let core: Promise<HighlighterCore> | null = null;
const loaded = new Set<string>();

function highlighter(): Promise<HighlighterCore> {
  core ??= createHighlighterCore({ themes: [theme], langs: [], engine: createJavaScriptRegexEngine() });
  return core;
}

/** Returns shiki HTML (already escaped), or null when the language is unknown. */
export async function highlightCode(code: string, lang: string): Promise<string | null> {
  const key = normalizeLang(lang);
  if (!key) return null;
  const hl = await highlighter();
  if (!loaded.has(key)) {
    const mod = (await LOADERS[key]?.()) as { default: never };
    await hl.loadLanguage(mod.default);
    loaded.add(key);
  }
  const names = hl.getLoadedLanguages();
  const target = names.includes(key) ? key : (names.find((n) => n.startsWith(key)) ?? "text");
  return hl.codeToHtml(code, { lang: target, theme: "dot" });
}
