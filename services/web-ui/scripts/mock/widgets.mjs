// Widget scenarios: one builder per `Present` kind, plus hostile variants for graceful-degradation tests.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const table = () => ({
  columns: [{ key: "service", label: "Service" }, { key: "region", label: "Region" }, { key: "requests", label: "Requests", type: "number" }, { key: "p95", label: "p95 ms", type: "number" }, { key: "errors", label: "Error %", type: "number" }],
  rows: Array.from({ length: 12 }, (_, i) => ({ service: ["api", "auth", "search", "billing", "web", "worker"][i % 6] + `-${i + 1}`, region: ["eu-west", "us-east", "ap-south"][i % 3], requests: 120000 + i * 8731, p95: 80 + ((i * 37) % 210), errors: i === 4 ? null : Number(((i * 0.173) % 2).toFixed(2)) })),
  caption: "Service health, last 24 hours",
});

const chart = (type) => {
  const pts = (f) => MONTHS.map((x, i) => ({ x, y: Math.round(f(i)) }));
  if (type === "pie") return { type, series: [{ name: "Traffic", points: [["Web", 46], ["iOS", 24], ["Android", 18], ["API", 9], ["Other", 3]].map(([x, y]) => ({ x, y })) }], unit: "%" };
  if (type === "line") return { type, series: [{ name: "Latency", points: pts((i) => 120 + Math.sin(i) * 30 + i * 4) }, { name: "Errors", points: pts((i) => 20 + Math.cos(i) * 8) }, { name: "Queue", points: pts((i) => 60 + (i % 4) * 11) }], x_label: "Month", y_label: "ms", unit: "ms" };
  if (type === "area") return { type, series: [{ name: "Reads", points: pts((i) => 300 + i * 40) }, { name: "Writes", points: pts((i) => 120 + i * 15) }], x_label: "Month", y_label: "ops" };
  return { type: "bar", series: [{ name: "Revenue", points: pts((i) => 40 + ((i * 53) % 90)) }], x_label: "Month", y_label: "k USD", unit: "k" };
};

const stats = () => ({ items: [{ label: "Requests", value: 1284330, delta: 12.4, hint: "vs last week" }, { label: "p95 latency", value: 184, unit: "ms", delta: -6.1 }, { label: "Error rate", value: "0.42", unit: "%", delta: 0 }, { label: "Uptime", value: "99.98%", hint: "30 days" }] });
const steps = () => ({ items: [{ title: "Read the project layout", detail: "12 files scanned", status: "done" }, { title: "Write the failing test", status: "done" }, { title: "Implement setup_logging()", detail: "In progress", status: "active" }, { title: "Wire it into main()", status: "todo" }, { title: "Run the full suite", detail: "Failed once on CI", status: "error" }] });
const checklist = () => ({ items: [{ text: "Pin dependency versions", done: true }, { text: "Add healthchecks", done: true }, { text: "Rotate the API token", done: false }, { text: "Write the runbook", done: false }, { text: "Enable backups", done: false }] });
const cards = () => ({ items: [{ title: "Qwen3 Coder 30B", body: "Default coding model, fast on one GPU.", badge: "active", meta: [{ label: "Size", value: "18 GB" }, { label: "Quant", value: "Q4_K_M" }] }, { title: "Gemma 3 27B", body: "Good for Russian and Uzbek text.", badge: "idle", meta: [{ label: "Size", value: "16 GB" }] }, { title: "Whisper large-v3", body: "Speech to text.", meta: [] }, { title: "Embedding model", badge: "new" }] });
const callout = (level) => ({ level, title: { info: "Heads up", success: "All good", warning: "Careful", danger: "Destructive action" }[level], body: { info: "The index is rebuilt every night at 03:30.", success: "Migration applied to 3 databases.", warning: "This setting resets after a restart.", danger: "This will delete the build directory permanently." }[level] });
const tabs = () => ({ tabs: [{ label: "Overview", body: "## Overview\n\nDot is a **self-hosted** agent.\n\n- local models\n- no telemetry" }, { label: "Install", body: "```bash\nuv sync\nuv run dot serve\n```" }, { label: "Notes", body: "| key | value |\n|---|---|\n| port | 8765 |\n| mode | default |" }] });
const accordion = () => ({ items: [{ title: "What is Dot?", body: "A self-hosted coding and research agent." }, { title: "Where do files go?", body: "Into the per-session workspace, see the **Files** panel." }, { title: "Can it browse the web?", body: "Yes, through `WebFetch`. Results are marked tainted." }, { title: "Oʻzbekcha savol", body: "Gʻoya va oʻrik haqida qisqa javob." }] });
const choices = () => ({ options: ["Show me the details", "Summarize in one line", "Do it for all files"] });

const BUILD = { table, chart, stats, steps, checklist, cards, callout, tabs, accordion, choices };
const XSS = "<img src=x onerror=alert(1)>";

/** Hostile widgets: [kind, title, props]. */
function hostile() {
  const rows = (n) => Array.from({ length: n }, (_, i) => ({ a: i, b: `row ${i}`, c: i * 1.5, d: null, e: i % 2 ? "yes" : "no" }));
  const cols = ["a", "b", "c", "d", "e"].map((key) => ({ key, label: key.toUpperCase(), type: key === "b" || key === "e" ? "text" : "number" }));
  return [
    ["table", "Invalid props", { columns: "oops", rows: 12345 }],
    ["hologram", "Unknown kind", { x: 1 }],
    ["table", null, null],
    ["callout", XSS, { level: "danger", title: XSS, body: `${XSS} <script>alert(2)</script> **bold**` }],
    ["cards", "HTML cards", { items: [{ title: XSS, body: `[click](javascript:alert(1)) <a href="javascript:alert(1)">x</a>`, badge: XSS, meta: [{ label: XSS, value: "javascript:alert(1)" }] }] }],
    ["tabs", "Links", { tabs: [{ label: XSS, body: "[bad](javascript:alert(1)) ![i](javascript:alert(1)) <iframe src=javascript:alert(1)></iframe>" }] }],
    ["callout", "100k string", { level: "info", title: "T".repeat(100000), body: "A".repeat(100000) }],
    ["table", "5000 rows", { columns: cols, rows: rows(5000) }],
    ["table", "20 columns", { columns: Array.from({ length: 20 }, (_, i) => ({ key: `k${i}`, label: `Column ${i}` })), rows: [Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`k${i}`, i]))] }],
    ["chart", "Radar and 9 series", { type: "radar", series: Array.from({ length: 9 }, (_, s) => ({ name: `s${s}`, points: Array.from({ length: 300 }, (_, i) => ({ x: i, y: Math.sin(i / 9 + s) * 50 })) })) }],
    ["chart", "NaN points", { type: "line", series: [{ name: "bad", points: [{ x: "a", y: "not a number" }, { x: null, y: null }, { y: 3 }] }] }],
    ["stats", "Items is an object", { items: { label: "x" } }],
    ["steps", "Weird status", { items: [{ title: "ok", status: "weird" }, { title: 5 }, null] }],
    ["cards", "60 cards", { items: Array.from({ length: 60 }, (_, i) => ({ title: `Card ${i}`, body: "b" })) }],
    ["choices", "Bad options", { options: [1, null, { label: "x" }, "x".repeat(5000)] }],
    ["checklist", "Not an array", { items: "nope" }],
  ];
}

/** @returns {Promise<boolean>} true when the prompt is a widget prompt. */
export async function widgetScenario(text, c) {
  const { present } = c;
  if (/badwidget/i.test(text)) {
    await c.tok("Sending hostile widgets. The UI should degrade, not crash.\n");
    for (const [k, t, p] of hostile()) await present(k, t ?? undefined, p);
    await c.tok("Done.");
    return true;
  }
  if (/\bwidgets\b/i.test(text)) {
    await c.tok("Here is every widget kind.\n");
    for (const kind of ["table", "stats", "steps", "checklist", "cards", "tabs", "accordion"]) await present(kind, `${kind} widget`, BUILD[kind]());
    for (const t of ["bar", "line", "area", "pie"]) await present("chart", `chart (${t})`, chart(t));
    for (const l of ["info", "success", "warning", "danger"]) await present("callout", undefined, callout(l));
    await present("choices", "Pick one", choices());
    await c.tok("That was all of them.");
    return true;
  }
  const kind = Object.keys(BUILD).find((k) => new RegExp(`\\b${k}\\b`, "i").test(text));
  if (!kind) return false;
  await c.tok(`Here is a ${kind} widget.\n`);
  if (kind === "chart") {
    const type = /\bchart\s+(bar|line|area|pie)\b/i.exec(text)?.[1]?.toLowerCase() ?? "bar";
    await present("chart", `Chart (${type})`, chart(type));
  } else if (kind === "callout") {
    for (const l of ["info", "success", "warning", "danger"]) await present("callout", undefined, callout(l));
  } else await present(kind, `${kind[0].toUpperCase()}${kind.slice(1)}`, BUILD[kind]());
  if (kind !== "choices") await c.tok("Let me know if you want it changed.");
  return true;
}
