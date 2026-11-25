// Form questions (`question.fields`) and the legacy option question, plus POST /v1/questions/{id}/answer.
import { st, nid, json, readBody } from "./core.mjs";

const opt = (label, description) => ({ label, ...(description ? { description } : {}) });
export const FIELDS = [
  { id: "framework", type: "single_select", label: "Framework", help: "Pick the web framework.", required: true, options: [opt("FastAPI", "Async, typed"), opt("Django", "Batteries included"), opt("Flask")] },
  { id: "checks", type: "multi_select", label: "Checks to run", options: [opt("lint"), opt("types", "mypy strict"), opt("tests"), opt("security")], default: ["lint"] },
  { id: "notes", type: "text", label: "Notes", help: "Up to 200 characters.", multiline: true, placeholder: "Anything else?", max: 200 },
  { id: "workers", type: "number", label: "Workers", required: true, min: 1, max: 16, step: 1, default: 4 },
  { id: "temperature", type: "slider", label: "Temperature", min: 0, max: 100, step: 5, default: 30 },
  { id: "dry_run", type: "toggle", label: "Dry run", default: true },
  { id: "deadline", type: "date", label: "Deadline" },
  { id: "priority", type: "rank", label: "Rank the priorities", required: true, options: [opt("Speed"), opt("Cost"), opt("Quality"), opt("Safety")] },
];

const labels = (f) => (f.options ?? []).map((o) => o.label);
const empty = (v) => v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length);

/** @returns {string[]} human-readable problems (empty when valid). */
export function validate(fields, a) {
  const bad = [];
  if (!a || typeof a !== "object" || Array.isArray(a)) return ["fields must be an object"];
  for (const f of fields) {
    const v = a[f.id];
    if (empty(v)) { if (f.required) bad.push(`${f.id}: required`); continue; }
    const range = (x) => (f.min !== undefined && x < f.min) || (f.max !== undefined && x > f.max);
    if (f.type === "single_select" && !labels(f).includes(v)) bad.push(`${f.id}: unknown option`);
    else if (f.type === "multi_select" && !(Array.isArray(v) && v.every((x) => labels(f).includes(x)))) bad.push(`${f.id}: unknown option`);
    else if (f.type === "text" && (typeof v !== "string" || range(v.length))) bad.push(`${f.id}: text length out of range`);
    else if ((f.type === "number" || f.type === "slider") && (typeof v !== "number" || !Number.isFinite(v) || range(v))) bad.push(`${f.id}: must be a number in ${f.min}..${f.max}`);
    else if (f.type === "toggle" && typeof v !== "boolean") bad.push(`${f.id}: must be boolean`);
    else if (f.type === "date" && !(typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v) && !Number.isNaN(Date.parse(v)))) bad.push(`${f.id}: must be an ISO date`);
    else if (f.type === "rank" && !(Array.isArray(v) && v.length === labels(f).length && new Set(v).size === v.length && v.every((x) => labels(f).includes(x)))) bad.push(`${f.id}: must rank every option once`);
  }
  return bad;
}

const toolCall = (c, name) => {
  const call_id = `call_${nid()}`;
  c.send({ type: "tool_call", invocation: { call_id, name, arguments: { questions: [] } } });
  return call_id;
};
const toolResult = (c, call_id, output) => {
  c.send({ type: "tool_result", result: { call_id, output, is_error: false, tainted: false, spill_path: null } });
  c.acc.calls.push({ call_id, name: "AskUserQuestion", args: { questions: [] }, output });
};

export async function formScenario(c) {
  const call_id = toolCall(c, "AskUserQuestion");
  const question_id = `Q${nid()}`;
  c.send({ type: "question", question_id, question: "Fill in the deployment settings.", options: [], multi_select: false, fields: FIELDS });
  const a = await c.block(new Promise((r) => st.answers.set(question_id, { fields: FIELDS, r })));
  toolResult(c, call_id, `User answered: ${typeof a === "string" ? a : JSON.stringify(a)}`);
  await c.tok(`Got it: ${typeof a === "string" ? a : `${a.framework} with ${a.workers} workers`}.`);
  return true;
}

/** Legacy single/multi question with options. */
export async function askScenario(text, c) {
  const call_id = toolCall(c, "AskUserQuestion");
  const question_id = `Q${nid()}`;
  const multi = /multi/i.test(text);
  c.send({ type: "question", question_id, question: multi ? "Which checks should I run before committing?" : "Which logging library should I use for the CLI?", options: [{ label: "stdlib logging", description: "No new dependency, enough for this tool." }, { label: "structlog", description: "Structured output, adds a dependency." }, { label: "loguru", description: "" }], multi_select: multi });
  const a = await c.block(new Promise((r) => st.answers.set(question_id, { options: ["stdlib logging", "structlog", "loguru"], multi, r })));
  toolResult(c, call_id, `User answered: ${a}`);
  await c.tok(`Going with ${a}.`);
  return true;
}

export async function formRoutes(req, res, p, url, fail) {
  const m = /^\/v1\/questions\/([^/]+)\/answer$/.exec(p);
  if (!m) return false;
  const q = st.answers.get(m[1]);
  if (!q) return fail(2003, "Question not found", 404) ?? true;
  const body = await readBody(req);
  if (q.fields) {
    const bad = validate(q.fields, body.fields);
    if (bad.length) return fail(2005, `Answer is not valid: ${bad.join("; ")}`, 400) ?? true;
    st.answers.delete(m[1]);
    q.r(JSON.stringify(body.fields));
    return json(res, 200, { ok: true }), true;
  }
  const { selected = [], other = null } = body;
  if ((!selected.length && !other) || selected.some((x) => !q.options.includes(x)) || (!q.multi && selected.length > 1)) return fail(2005, "Answer is not valid", 400) ?? true;
  st.answers.delete(m[1]);
  q.r([...selected, ...(other ? [other] : [])].join(", "));
  return json(res, 200, { ok: true }), true;
}
