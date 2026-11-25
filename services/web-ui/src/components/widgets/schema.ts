// Hand-written validators for display widgets. Anything outside the caps returns null and the caller degrades to a code block.
export const CAPS = { rows: 200, cols: 12, series: 8, points: 200, items: 30, str: 2000 } as const;

export type Cell = string | number | null;
export interface TableP { columns: { key: string; label: string; num: boolean }[]; rows: Record<string, Cell>[]; caption?: string }
export type ChartType = "bar" | "line" | "area" | "pie";
export interface ChartP { type: ChartType; series: { name: string; points: { x: string; y: number }[] }[]; xLabel?: string; yLabel?: string; unit?: string }
export interface StatsP { items: { label: string; value: number | string; unit?: string; delta?: number; hint?: string }[] }
export type StepStatus = "done" | "active" | "todo" | "error";
export interface StepsP { items: { title: string; detail?: string; status: StepStatus }[] }
export interface ChecklistP { items: { text: string; done: boolean }[] }
export interface CardsP { items: { title: string; body?: string; badge?: string; meta: { label: string; value: string }[] }[] }
export type Level = "info" | "success" | "warning" | "danger";
export interface CalloutP { level: Level; title?: string; body: string }
export interface TabsP { tabs: { label: string; body: string }[] }
export interface AccordionP { items: { title: string; body: string }[] }
export interface ChoicesP { options: string[] }

const isRec = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, min = 0): string | null => (typeof v === "string" && v.length >= min && v.length <= CAPS.str ? v : null);
const optStr = (v: unknown): string | undefined | null => (v === undefined || v === null ? undefined : str(v));
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const list = (v: unknown, max: number = CAPS.items): unknown[] | null => (Array.isArray(v) && v.length > 0 && v.length <= max ? v : null);

/** Map every element; null when any element fails. */
function all<T>(v: unknown[], f: (x: unknown) => T | null): T[] | null {
  const out: T[] = [];
  for (const x of v) {
    const r = f(x);
    if (r === null) return null;
    out.push(r);
  }
  return out;
}

export function parseTable(p: unknown): TableP | null {
  if (!isRec(p)) return null;
  const cols = list(p.columns, CAPS.cols);
  const rows = Array.isArray(p.rows) && p.rows.length <= CAPS.rows ? p.rows : null;
  if (!cols || !rows) return null;
  const columns = all(cols, (c) => {
    if (!isRec(c)) return null;
    const key = str(c.key, 1), label = str(c.label);
    return key !== null && label !== null ? { key, label, num: c.type === "number" } : null;
  });
  if (!columns) return null;
  const rs = all(rows, (r) => {
    if (!isRec(r)) return null;
    const o: Record<string, Cell> = {};
    for (const c of columns) {
      const v = r[c.key];
      if (v === undefined || v === null) o[c.key] = null;
      else if (typeof v === "number" && Number.isFinite(v)) o[c.key] = v;
      else if (typeof v === "string" && v.length <= CAPS.str) o[c.key] = v;
      else return null;
    }
    return o;
  });
  const caption = optStr(p.caption);
  if (!rs || caption === null) return null;
  return { columns, rows: rs, ...(caption ? { caption } : {}) };
}

export function parseChart(p: unknown): ChartP | null {
  if (!isRec(p) || !(["bar", "line", "area", "pie"] as unknown[]).includes(p.type)) return null;
  const s = list(p.series, CAPS.series);
  if (!s) return null;
  const series = all(s, (x) => {
    if (!isRec(x)) return null;
    const name = str(x.name), pts = list(x.points, CAPS.points);
    if (name === null || !pts) return null;
    const points = all(pts, (q) => {
      if (!isRec(q)) return null;
      const y = num(q.y);
      const x2 = typeof q.x === "number" ? (Number.isFinite(q.x) ? String(q.x) : null) : str(q.x);
      return y === null || x2 === null ? null : { x: x2, y };
    });
    return points ? { name, points } : null;
  });
  const xl = optStr(p.x_label), yl = optStr(p.y_label), unit = optStr(p.unit);
  if (!series || xl === null || yl === null || unit === null) return null;
  const type = p.type as ChartType;
  return { type, series: type === "pie" ? series.slice(0, 1) : series, ...(xl ? { xLabel: xl } : {}), ...(yl ? { yLabel: yl } : {}), ...(unit ? { unit } : {}) };
}

export function parseStats(p: unknown): StatsP | null {
  if (!isRec(p)) return null;
  const l = list(p.items);
  const items = l && all(l, (x) => {
    if (!isRec(x)) return null;
    const label = str(x.label), unit = optStr(x.unit), hint = optStr(x.hint);
    const value = typeof x.value === "number" ? num(x.value) : str(x.value);
    const delta = x.delta === undefined || x.delta === null ? undefined : num(x.delta);
    if (label === null || value === null || unit === null || hint === null || delta === null) return null;
    return { label, value, ...(unit ? { unit } : {}), ...(delta !== undefined ? { delta } : {}), ...(hint ? { hint } : {}) };
  });
  return items ? { items } : null;
}

export function parseSteps(p: unknown): StepsP | null {
  if (!isRec(p)) return null;
  const l = list(p.items);
  const items = l && all(l, (x) => {
    if (!isRec(x)) return null;
    const title = str(x.title, 1), detail = optStr(x.detail);
    if (title === null || detail === null || !(["done", "active", "todo", "error"] as unknown[]).includes(x.status)) return null;
    return { title, status: x.status as StepStatus, ...(detail ? { detail } : {}) };
  });
  return items ? { items } : null;
}

export function parseChecklist(p: unknown): ChecklistP | null {
  if (!isRec(p)) return null;
  const l = list(p.items);
  const items = l && all(l, (x) => {
    if (!isRec(x) || typeof x.done !== "boolean") return null;
    const text = str(x.text, 1);
    return text === null ? null : { text, done: x.done };
  });
  return items ? { items } : null;
}

export function parseCards(p: unknown): CardsP | null {
  if (!isRec(p)) return null;
  const l = list(p.items);
  const items = l && all(l, (x) => {
    if (!isRec(x)) return null;
    const title = str(x.title, 1), body = optStr(x.body), badge = optStr(x.badge);
    if (title === null || body === null || badge === null) return null;
    const m = x.meta === undefined || x.meta === null ? [] : Array.isArray(x.meta) && x.meta.length <= 12 ? x.meta : null;
    const meta = m && all(m, (y) => {
      if (!isRec(y)) return null;
      const label = str(y.label), value = typeof y.value === "number" ? String(y.value) : str(y.value);
      return label === null || value === null ? null : { label, value };
    });
    return meta ? { title, meta, ...(body ? { body } : {}), ...(badge ? { badge } : {}) } : null;
  });
  return items ? { items } : null;
}

export function parseCallout(p: unknown): CalloutP | null {
  if (!isRec(p) || !(["info", "success", "warning", "danger"] as unknown[]).includes(p.level)) return null;
  const body = str(p.body, 1), title = optStr(p.title);
  if (body === null || title === null) return null;
  return { level: p.level as Level, body, ...(title ? { title } : {}) };
}

export function parseTabs(p: unknown): TabsP | null {
  if (!isRec(p)) return null;
  const l = list(p.tabs, 12);
  const tabs = l && all(l, (x) => {
    if (!isRec(x)) return null;
    const label = str(x.label, 1), body = str(x.body);
    return label === null || body === null ? null : { label, body };
  });
  return tabs ? { tabs } : null;
}

export function parseAccordion(p: unknown): AccordionP | null {
  if (!isRec(p)) return null;
  const l = list(p.items);
  const items = l && all(l, (x) => {
    if (!isRec(x)) return null;
    const title = str(x.title, 1), body = str(x.body);
    return title === null || body === null ? null : { title, body };
  });
  return items ? { items } : null;
}

export function parseChoices(p: unknown): ChoicesP | null {
  if (!isRec(p)) return null;
  const l = list(p.options, 12);
  const options = l && all(l, (x) => str(x, 1));
  return options ? { options } : null;
}

export const PARSERS = {
  table: parseTable, chart: parseChart, stats: parseStats, steps: parseSteps, checklist: parseChecklist,
  cards: parseCards, callout: parseCallout, tabs: parseTabs, accordion: parseAccordion, choices: parseChoices,
} as const;
export type WidgetKind = keyof typeof PARSERS;
export const isWidgetKind = (k: string): k is WidgetKind => Object.hasOwn(PARSERS, k);

export function formatNum(n: number, unit?: string): string {
  const s = Math.abs(n) >= 1e4 || Number.isInteger(n) ? n.toLocaleString("en-US", { maximumFractionDigits: 0 }) : n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return unit ? `${s}${unit.length <= 2 ? "" : " "}${unit}` : s;
}
