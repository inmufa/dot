const DAY = 86_400_000;
const startOfDay = (d: Date): number => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

/** Index-style stamp: "14:02" today, weekday within the week, "Nov 18" (plus year when old) otherwise. */
export function indexTime(iso: string | undefined, now: Date = new Date()): string {
  const t = iso ? Date.parse(iso) : NaN;
  if (!Number.isFinite(t)) return "";
  const d = new Date(t);
  const today = startOfDay(now);
  if (t >= today) return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  if (t >= today - 6 * DAY) return d.toLocaleDateString("en-US", { weekday: "short" });
  const md = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return d.getFullYear() === now.getFullYear() ? md : `${md} ${d.getFullYear()}`;
}

/** Group label: lowercase, short. */
export const GROUP_LABEL: Record<string, string> = { Pinned: "pinned", Today: "today", Yesterday: "yesterday", "Previous 7 days": "this week", Older: "older" };
