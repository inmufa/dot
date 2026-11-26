// 5-field cron, same subset as the backend scheduler. Times are browser-local.
export interface CronFields {
  minute: number[];
  hour: number[];
  dom: number[];
  month: number[];
  dow: number[];
  domStar: boolean;
  dowStar: boolean;
}
export type CronResult = { ok: true; fields: CronFields } | { ok: false; error: string };

const MACROS: Record<string, string> = {
  "@hourly": "0 * * * *",
  "@daily": "0 0 * * *",
  "@midnight": "0 0 * * *",
  "@weekly": "0 0 * * 0",
  "@monthly": "0 0 1 * *",
  "@yearly": "0 0 1 1 *",
  "@annually": "0 0 1 1 *",
};
const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const MONTH_NAME = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_NAME = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function value(tok: string, names: string[], base: number): number {
  const i = names.indexOf(tok.toLowerCase());
  if (i >= 0) return i + base;
  if (!/^\d{1,3}$/.test(tok)) throw new Error(`"${tok.slice(0, 20)}" is not a number`);
  return Number(tok);
}

function field(src: string, label: string, [lo, hi]: [number, number], names: string[] = []): number[] {
  const base = lo;
  const out = new Set<number>();
  for (const part of src.split(",")) {
    const [range = "", stepS, extra] = part.split("/");
    if (extra !== undefined || range === "") throw new Error(`${label}: bad item "${part.slice(0, 20)}"`);
    const step = stepS === undefined ? 1 : Number(stepS);
    if (!Number.isInteger(step) || step < 1) throw new Error(`${label}: step must be 1 or more`);
    let a = lo;
    let b = hi;
    if (range !== "*") {
      const [x = "", y, z] = range.split("-");
      if (z !== undefined) throw new Error(`${label}: bad range`);
      a = value(x, names, base);
      b = y === undefined ? (stepS === undefined ? a : hi) : value(y, names, base);
    }
    if (a < lo || b > hi || a > b) throw new Error(`${label}: must be ${lo}-${hi}`);
    for (let v = a; v <= b; v += step) out.add(v);
  }
  return [...out].sort((p, q) => p - q);
}

export function parseCron(raw: string): CronResult {
  const src = MACROS[raw.trim().toLowerCase()] ?? raw.trim();
  const parts = src.split(/\s+/);
  if (parts.length !== 5 || parts[0] === "") return { ok: false, error: "Needs 5 fields: minute hour day month weekday." };
  const [mi = "", ho = "", dm = "", mo = "", dw = ""] = parts;
  try {
    const dow = field(dw, "weekday", [0, 7], DAYS).map((d) => d % 7);
    return {
      ok: true,
      fields: {
        minute: field(mi, "minute", [0, 59]),
        hour: field(ho, "hour", [0, 23]),
        dom: field(dm, "day", [1, 31]),
        month: field(mo, "month", [1, 12], MONTHS),
        dow: [...new Set(dow)].sort((p, q) => p - q),
        domStar: dm.startsWith("*"),
        dowStar: dw.startsWith("*"),
      },
    };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Invalid cron." };
  }
}

const pad = (n: number): string => String(n).padStart(2, "0");

function runs(nums: number[], name: (n: number) => string): string {
  const parts: string[] = [];
  for (let i = 0; i < nums.length; ) {
    let j = i;
    while (j + 1 < nums.length && nums[j + 1] === (nums[j] ?? 0) + 1) j++;
    const a = nums[i] ?? 0;
    const b = nums[j] ?? 0;
    if (j - i >= 2) parts.push(`${name(a)}-${name(b)}`);
    else for (let k = i; k <= j; k++) parts.push(name(nums[k] ?? 0));
    i = j + 1;
  }
  return parts.join(", ");
}

export function describeCron(f: CronFields): string {
  const allMin = f.minute.length === 60;
  const allHour = f.hour.length === 24;
  let time: string;
  if (allMin && allHour) time = "Every minute";
  else if (allHour) {
    const step = f.minute.length > 1 && f.minute.every((m, i) => m === i * (f.minute[1] ?? 1)) ? f.minute[1] : 0;
    time = allMin ? "Every minute" : step ? `Every ${step} minutes` : f.minute.length === 1 && f.minute[0] === 0 ? "Every hour, on the hour" : `Every hour at minute ${f.minute.join(", ")}`;
  } else if (f.minute.length * f.hour.length <= 4) {
    time = `At ${f.hour.flatMap((h) => f.minute.map((m) => `${pad(h)}:${pad(m)}`)).join(", ")}`;
  } else {
    time = `At minute ${runs(f.minute, String)} past hour ${runs(f.hour, String)}`;
  }
  const dayBits: string[] = [];
  if (!f.dowStar) dayBits.push(runs(f.dow, (d) => DAY_NAME[d] ?? String(d)));
  if (!f.domStar) dayBits.push(`day ${runs(f.dom, String)} of the month`);
  let days = dayBits.length ? ` on ${dayBits.join(" or ")}` : f.month.length === 12 && time.startsWith("At") ? ", every day" : "";
  if (f.month.length < 12) days += ` in ${runs(f.month, (m) => MONTH_NAME[m - 1] ?? String(m))}`;
  return time + days;
}

function firstAfter(f: CronFields, day: Date, from: Date): Date | null {
  for (const h of f.hour) {
    const t = f.minute.map((m) => new Date(day.getFullYear(), day.getMonth(), day.getDate(), h, m)).find((x) => x > from);
    if (t) return t;
  }
  return null;
}

/** First run strictly after `from`, or null when none within about two years. */
export function nextRun(f: CronFields, from: Date): Date | null {
  const day = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  for (let i = 0; i < 800; i++, day.setDate(day.getDate() + 1)) {
    if (!f.month.includes(day.getMonth() + 1)) continue;
    const domOk = f.dom.includes(day.getDate());
    const dowOk = f.dow.includes(day.getDay());
    if (!(f.domStar || f.dowStar ? domOk && dowOk : domOk || dowOk)) continue;
    const t = firstAfter(f, day, from);
    if (t) return t;
  }
  return null;
}

export function describeCronText(src: string): { text: string; next: Date | null } | { error: string } {
  const r = parseCron(src);
  if (!r.ok) return { error: r.error };
  return { text: describeCron(r.fields), next: nextRun(r.fields, new Date()) };
}
