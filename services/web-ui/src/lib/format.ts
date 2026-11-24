export function compactTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 100_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${Math.round(n / 1000)}k`;
}

export function percent(used: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((used / limit) * 100)));
}

export function relativeTime(iso: string, now = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 45) return "now";
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86_400) return `${Math.round(s / 3600)}h`;
  if (s < 30 * 86_400) return `${Math.round(s / 86_400)}d`;
  return new Date(t).toISOString().slice(0, 10);
}

export function clip(text: string, max: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

const ARG_KEYS = ["command", "file_path", "path", "pattern", "url", "query", "name", "skill", "description", "plan"];

/** One-line summary of tool arguments for a collapsed row. */
export function shortArgs(args: Record<string, unknown>, max = 90): string {
  for (const k of ARG_KEYS) {
    const v = args[k];
    if (typeof v === "string" && v) return clip(v, max);
  }
  const keys = Object.keys(args);
  if (!keys.length) return "";
  return clip(JSON.stringify(args), max);
}

export function sessionTitle(title: string | null): string {
  return title?.trim() ? title.trim() : "New session";
}
