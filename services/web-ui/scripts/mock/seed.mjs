// Seed sessions (Today / Yesterday / week / older, pinned, archived, mixed languages) and the worst-case set.
import { st, newSession, add, persistTurn, age, nid } from "./core.mjs";
import { seedFiles } from "./files.mjs";
import { SOURCES } from "./research.mjs";
import { seedProjects, resetFeatures } from "./features.mjs";

const DAY = 1440;
const sinceMidnight = () => { const d = new Date(); return Math.max(1, Math.floor((Date.now() - new Date(d).setHours(0, 0, 0, 0)) / 60_000) - 1); };
/** Minutes ago for "today" (clamped to after midnight) or noon of N days ago. */
const ago = (days, extra = 0) => {
  if (days === 0) return Math.min(extra, sinceMidnight());
  const noon = new Date(); noon.setHours(12, 0, 0, 0);
  return Math.floor((Date.now() - noon.getTime()) / 60_000) + (days - 1) * DAY + extra;
};

const TABLE = { columns: [{ key: "q", label: "Query" }, { key: "ms", label: "ms", type: "number" }], rows: [{ q: "orders by user", ms: 840 }, { q: "orders by day", ms: 120 }], caption: "Slow queries" };

// [title, days, extraMin, opts, user, assistant, extras]
const SEEDS = [
  ["Add structured logging to the CLI", 0, 5, { pinned: true, project: "Dot", state: "running" }, "Add structured logging to the CLI", "I added `setup_logging(verbose)` and wired it into `main()`.", { thinking: "The CLI has no logging. A small setup function is enough.", calls: [{ name: "Read", args: { file_path: "src/app.py" }, output: "     1\timport sys" }] }],
  ["Почему падает тест test_retry", 0, 40, { project: "Dot", state: "waiting" }, "Почему падает тест test_retry?", "Тест зависит от реального времени. Замените `sleep` на фейковые часы."],
  ["Oʻzbekcha interfeys tarjimasi", 0, 120, { project: "Kigo" }, "Interfeys matnlarini oʻzbekchaga tarjima qil: gʻoya, oʻrik, qoʻshish.", "Tarjima tayyor: gʻoya - идея, oʻrik - слива, qoʻshish - добавить."],
  ["Refactor auth middleware", 1, 0, { project: "Dot" }, "Refactor the auth middleware to use dependency injection.", "Done. The middleware now takes a `TokenVerifier` and tests use a fake."],
  ["Gʻoya: oylik hisobot generatori", 1, 90, {}, "Oylik hisobot generatori uchun gʻoya ber.", "Jadval va grafik bilan PDF hisobot: sotuvlar, xarajatlar, oʻsish."],
  ["Разобрать лог nginx за ночь", 1, 200, { project: "Docs" }, "Разбери лог nginx за ночь, где 502?", "Всплеск 502 в 03:12, апстрим перезапускался. Нужен healthcheck."],
  ["Migrate settings to pydantic v2", 3, 0, { project: "Dot" }, "Migrate settings to pydantic v2.", "Replaced `BaseSettings` import and `Config` class with `SettingsConfigDict`."],
  ["Docker compose healthchecks", 4, 0, {}, "Add healthchecks to docker compose.", "Added `pg_isready` and an HTTP check for the API."],
  ["SQL: slow query on orders", 5, 0, { pinned: true, project: "Kigo" }, "Why is the orders query slow?", "A missing index on `orders(user_id, created_at)`.", { widget: ["table", "Slow queries", TABLE] }],
  ["Обзор архитектуры RAG", 20, 0, { project: "Docs" }, "Обзор архитектуры RAG для документов.", "Чанкинг, эмбеддинги, поиск, переранжирование, ответ с цитатами [1][2].", { sources: SOURCES.slice(0, 2) }],
  ["Quarterly report draft", 35, 0, {}, "Draft the quarterly report outline.", "1. Highlights 2. Metrics 3. Risks 4. Plan."],
  ["Oʻrik bogʻi kuzatuv skripti", 48, 0, {}, "Oʻrik bogʻi uchun sensor kuzatuv skripti yoz.", "Skript har 10 daqiqada namlikni oʻqiydi va CSV ga yozadi."],
  ["Regex cheat sheet", 60, 0, {}, "Give me a regex cheat sheet.", "`\\d+` digits, `\\w+` word chars, `(?<name>...)` named group."],
  ["Old experiment: tokenizer bench", 75, 0, { archived: true }, "Benchmark the tokenizers.", "tiktoken was 3x faster than the pure Python version."],
];

function build([title, days, extra, o, user, reply, x = {}]) {
  const s = newSession({ title, project: o.project });
  Object.assign(s, { pinned: !!o.pinned, archived: !!o.archived, state: o.state ?? "idle" });
  add(s, { role: "user", content: user });
  const acc = { text: reply, thinking: x.thinking ?? "", calls: [], widgets: [], sources: x.sources ?? null };
  for (const c of x.calls ?? []) acc.calls.push({ call_id: `call_${nid()}`, ...c });
  if (x.widget) { const [kind, t, props] = x.widget; const call_id = `call_${nid()}`; acc.calls.push({ call_id, name: "Present", args: { kind, title: t, props }, output: `Displayed ${kind} widget` }); acc.widgets.push({ call_id, kind, title: t, props }); }
  persistTurn(s, acc);
  age(s, ago(days, extra));
  return s;
}

export function seedSessions() {
  st.sessions.clear(); st.files.clear(); st.uploads.clear();
  seedProjects();
  resetFeatures();
  const made = SEEDS.map(build);
  st.sessions.clear();
  made.forEach((s, i) => { if (i === 0) s.id = "SEED000001"; st.sessions.set(s.id, s); });
  seedFiles(made[0].id);
}

const LONGW = "very-long-unbroken-title-".repeat(14);
const TITLES = [
  (i) => `${LONGW}${i}`,
  (i) => `مرحبا بالعالم - عنوان طويل جدا للاختبار رقم ${i} ثم المزيد من النص`,
  (i) => `🚀🔥✨ Эмодзи-тест ${i} 😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀`,
  (i) => `Очень длинное название сессии про разбор логов и настройку кластера номер ${i}, чтобы проверить обрезание`,
  (i) => `Oʻzbekiston gʻoyalari: oʻrik, gʻisht, qoʻshimcha, shoʻrva va boshqa soʻzlar ${i} ${"gʻoya ".repeat(12)}`,
  (i) => `Session ${i}`,
];

export function addWorst() {
  const rows = Array.from({ length: 300 }, (_, i) => `| row ${i} | ${"cell ".repeat(8)} | ${i * 3.14} |`).join("\n");
  for (let i = 0; i < 500; i++) {
    const s = newSession({ title: TITLES[i % TITLES.length](i), project: i % 7 === 0 ? "Dot" : null });
    s.worst = true; s.pinned = i % 40 === 0; s.archived = i % 97 === 0; s.state = ["idle", "idle", "running", "waiting"][i % 4];
    add(s, { role: "user", content: `Worst case ${i}` });
    const big = i % 50 === 0;
    const acc = { text: big ? `| a | b | c |\n|---|---|---|\n${rows}\n` : `Reply ${i}`, thinking: "", calls: [], widgets: [], sources: null };
    if (big) {
      const call_id = `call_${nid()}`;
      const props = { columns: ["a", "b", "c", "d", "e", "f"].map((key) => ({ key, label: key, type: key === "a" ? "number" : "text" })), rows: Array.from({ length: 200 }, (_, r) => Object.fromEntries(["a", "b", "c", "d", "e", "f"].map((k) => [k, k === "a" ? r : `${k}${r} ${"x".repeat(30)}`]))) };
      acc.calls.push({ call_id, name: "Present", args: { kind: "table", title: "Huge table", props }, output: "Displayed table widget" });
      acc.widgets.push({ call_id, kind: "table", title: "Huge table", props });
    }
    persistTurn(s, acc);
    age(s, 5 + i * 53);
  }
}

export const dropWorst = () => { for (const [id, s] of st.sessions) if (s.worst) st.sessions.delete(id); };
