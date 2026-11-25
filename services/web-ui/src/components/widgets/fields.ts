// Ask-form field schema, draft state and validation (contract: ui-contract.md "Form fields").
export type FieldType = "single_select" | "multi_select" | "text" | "number" | "slider" | "toggle" | "date" | "rank";
export interface Opt { label: string; description?: string }
export interface Field {
  id: string; type: FieldType; label: string; help?: string; required: boolean; options: Opt[];
  min?: number; max?: number; step?: number; placeholder?: string; multiline: boolean; def: unknown;
}
/** Draft values: numbers stay strings while typing. */
export type Draft = Record<string, unknown>;

const TYPES: unknown[] = ["single_select", "multi_select", "text", "number", "slider", "toggle", "date", "rank"];
const isRec = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const s = (v: unknown, max = 500): string | undefined => (typeof v === "string" && v.length <= max ? v : undefined);
const n = (v: unknown): number | undefined => (typeof v === "number" && Number.isFinite(v) ? v : undefined);

export function parseFields(raw: unknown): Field[] | null {
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > 20) return null;
  const out: Field[] = [];
  const ids = new Set<string>();
  for (const r of raw) {
    if (!isRec(r) || !TYPES.includes(r.type)) return null;
    const id = s(r.id, 80), label = s(r.label);
    if (!id || !label || ids.has(id)) return null;
    ids.add(id);
    const type = r.type as FieldType;
    const options: Opt[] = [];
    if (Array.isArray(r.options)) {
      if (r.options.length > 30) return null;
      for (const o of r.options) {
        const l = typeof o === "string" ? o : isRec(o) ? s(o.label, 300) : undefined;
        if (!l) return null;
        const d = isRec(o) ? s(o.description, 500) : undefined;
        options.push({ label: l, ...(d ? { description: d } : {}) });
      }
    }
    if ((type === "single_select" || type === "multi_select" || type === "rank") && options.length === 0) return null;
    out.push({ id, type, label, required: r.required === true, options, multiline: r.multiline === true, def: r.default, help: s(r.help), min: n(r.min), max: n(r.max), step: n(r.step), placeholder: s(r.placeholder, 200) });
  }
  return out;
}

export function initialDraft(fs: Field[]): Draft {
  const d: Draft = {};
  for (const f of fs) {
    const labels = f.options.map((o) => o.label);
    switch (f.type) {
      case "single_select": d[f.id] = typeof f.def === "string" && labels.includes(f.def) ? f.def : null; break;
      case "multi_select": d[f.id] = Array.isArray(f.def) ? f.def.filter((x): x is string => typeof x === "string" && labels.includes(x)) : []; break;
      case "rank": d[f.id] = Array.isArray(f.def) && f.def.length === labels.length && labels.every((l) => (f.def as unknown[]).includes(l)) ? [...(f.def as string[])] : labels; break;
      case "toggle": d[f.id] = f.def === true; break;
      case "slider": d[f.id] = String(n(f.def) ?? f.min ?? 0); break;
      case "number": d[f.id] = n(f.def) !== undefined ? String(f.def) : ""; break;
      default: d[f.id] = typeof f.def === "string" ? f.def : "";
    }
  }
  return d;
}

const blank = (v: unknown): boolean => v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);

/** Per-field error text, or undefined when valid. */
export function fieldError(f: Field, v: unknown): string | undefined {
  if (blank(v)) return f.required ? "Required" : undefined;
  if (f.type === "text" && typeof v === "string") {
    if (f.max !== undefined && v.length > f.max) return `At most ${f.max} characters`;
    if (f.min !== undefined && v.length < f.min) return `At least ${f.min} characters`;
  }
  if (f.type === "number" || f.type === "slider") {
    const x = Number(v);
    if (!Number.isFinite(x)) return "Enter a number";
    if (f.min !== undefined && x < f.min) return `At least ${f.min}`;
    if (f.max !== undefined && x > f.max) return `At most ${f.max}`;
    if (f.type === "number" && f.step === 1 && !Number.isInteger(x)) return "Whole numbers only";
  }
  if (f.type === "date" && !(typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)))) return "Pick a valid date";
  return undefined;
}

export function validateDraft(fs: Field[], d: Draft): Record<string, string> {
  const e: Record<string, string> = {};
  for (const f of fs) { const m = fieldError(f, d[f.id]); if (m) e[f.id] = m; }
  return e;
}

/** Wire answer: only filled fields, numbers converted. */
export function toAnswer(fs: Field[], d: Draft): Record<string, unknown> {
  const a: Record<string, unknown> = {};
  for (const f of fs) {
    const v = d[f.id];
    if (f.type === "toggle") a[f.id] = v === true;
    else if (blank(v)) continue;
    else if (f.type === "number" || f.type === "slider") a[f.id] = Number(v);
    else a[f.id] = v;
  }
  return a;
}

export function summarize(fs: Field[], a: Record<string, unknown>): string {
  return fs.flatMap((f) => (f.id in a ? [`${f.label}: ${Array.isArray(a[f.id]) ? (a[f.id] as unknown[]).join(f.type === "rank" ? " > " : ", ") : typeof a[f.id] === "boolean" ? (a[f.id] ? "yes" : "no") : String(a[f.id])}`] : [])).join("; ").slice(0, 600);
}
