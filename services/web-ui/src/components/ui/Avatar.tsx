/** Initials disc; the colour is a stable pick per name. */
export function Avatar({ name, size = 28 }: { name: string; size?: number }) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const ini = ((words[0]?.[0] ?? "?") + (words.length > 1 ? (words[words.length - 1]?.[0] ?? "") : "")).toUpperCase();
  let h = 0;
  for (const ch of name) h = (h * 31 + (ch.codePointAt(0) ?? 0)) >>> 0;
  return <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.4, ["--av" as string]: `var(--chart-${(h % 6) + 1})` }} role="img" aria-label={name}>{ini}</span>;
}
