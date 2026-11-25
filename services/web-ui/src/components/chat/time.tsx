const hm = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });
const md = new Intl.DateTimeFormat("en", { month: "short", day: "numeric" });

export const clock = (at: number): string => hm.format(at);
export const fullDate = (at: number): string => new Date(at).toLocaleString(undefined, { dateStyle: "full", timeStyle: "medium" });
const dayKey = (at: number): string => new Date(at).toDateString();
export const sameDay = (a: number, b: number): boolean => dayKey(a) === dayKey(b);

/** "today", "yesterday" or "nov 18". */
export function dayLabel(at: number, now: number = Date.now()): string {
  if (sameDay(at, now)) return "today";
  if (sameDay(at, now - 86_400_000)) return "yesterday";
  return md.format(at).toLowerCase();
}

/** Gutter time. `dim` entries repeat the previous minute: hidden at rest, shown on hover or focus. */
export function Stamp({ at, dim }: { at: number | undefined; dim?: boolean }) {
  if (at === undefined) return null;
  return (
    <time className="stamp" dateTime={new Date(at).toISOString()} title={fullDate(at)} data-dim={dim || undefined}>
      {clock(at)}
    </time>
  );
}

/** Walks entries in order and flags a stamp as dim when it repeats the previous shown minute. */
export function stamper(first?: number): (at: number | undefined) => React.ReactNode {
  let last = first !== undefined ? clock(first) : "";
  return (at) => {
    if (at === undefined) return null;
    const c = clock(at);
    const dim = c === last;
    last = c;
    return <Stamp at={at} dim={dim} />;
  };
}
