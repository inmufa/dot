import type { SessionInfo } from "@/lib/api/types";

export type DayBucket = "Pinned" | "Today" | "Yesterday" | "Previous 7 days" | "Older";
export const BUCKETS: readonly DayBucket[] = ["Pinned", "Today", "Yesterday", "Previous 7 days", "Older"];

const startOfDay = (d: Date): number => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

export function bucketOf(iso: string, now: Date): Exclude<DayBucket, "Pinned"> {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "Older";
  const today = startOfDay(now);
  if (t >= today) return "Today";
  if (t >= today - 86_400_000) return "Yesterday";
  if (t >= today - 7 * 86_400_000) return "Previous 7 days";
  return "Older";
}

export const lastActive = (s: SessionInfo): string => s.updated_at ?? s.created_at;

/** Group sessions by recency; pinned ones first. Newest first inside each group. Empty groups are omitted. */
export function groupByDay(sessions: SessionInfo[], now: Date = new Date()): { bucket: DayBucket; items: SessionInfo[] }[] {
  const map = new Map<DayBucket, SessionInfo[]>();
  const sorted = [...sessions].filter((s) => !s.archived).sort((a, b) => Date.parse(lastActive(b)) - Date.parse(lastActive(a)));
  for (const s of sorted) {
    const b: DayBucket = s.pinned ? "Pinned" : bucketOf(lastActive(s), now);
    map.set(b, [...(map.get(b) ?? []), s]);
  }
  return BUCKETS.flatMap((b) => (map.has(b) ? [{ bucket: b, items: map.get(b) ?? [] }] : []));
}
