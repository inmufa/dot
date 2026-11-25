import { describe, expect, it } from "vitest";
import { describeCron, nextRun, parseCron, type CronFields } from "@/lib/util/cron";
import { parseEventJson, type StreamEvent } from "@/lib/stream/events";
import { itemsFromMessages } from "@/lib/stream/history";
import { chatReducer, initialChat, phaseOf, type ChatState } from "@/lib/stream/reducer";

const ev = (s: ChatState, e: StreamEvent, now = 1000): ChatState => chatReducer(s, { type: "event", event: e, now });
const start = (): ChatState => chatReducer(initialChat, { type: "send", text: "go" });
const sub = (label: string, status: "queued" | "started" | "step" | "finished", detail = ""): StreamEvent => ({ type: "subagent", label, subagent_type: "Explore", status, detail });
const q: StreamEvent = { type: "question", question_id: "Q1", question: "Which?", options: [{ label: "a", description: "" }, { label: "b", description: "x" }], multi_select: false };

describe("parsers for phase 4 events", () => {
  it("parses question, subagent and compaction", () => {
    expect(parseEventJson(JSON.stringify({ type: "question", question_id: "Q", question: "x", options: [{ label: "a" }, { nolabel: 1 }, { label: "b", description: "d" }], multi_select: true }))).toMatchObject({
      options: [{ label: "a", description: "" }, { label: "b", description: "d" }],
      multi_select: true,
    });
    expect(parseEventJson('{"type":"question","question_id":"Q","question":"x","options":[]}')).toBeNull();
    expect(parseEventJson('{"type":"subagent","label":"Explore 1","subagent_type":"Explore","status":"bogus"}')).toBeNull();
    expect(parseEventJson('{"type":"subagent","label":"Explore 1","subagent_type":"Explore","status":"step","detail":"Read"}')).toMatchObject({ status: "step", detail: "Read" });
    expect(parseEventJson('{"type":"compaction","tokens_before":12100,"tokens_after":4300,"stages":["summary",3]}')).toEqual({ type: "compaction", tokens_before: 12100, tokens_after: 4300, stages: ["summary"] });
  });
  it("caps options at 4 and tags approvals with the subagent", () => {
    const opts = Array.from({ length: 6 }, (_, i) => ({ label: `o${i}` }));
    const e4 = parseEventJson(JSON.stringify({ type: "question", question_id: "Q", question: "x", options: opts }));
    expect(e4?.type === "question" && e4.options.length).toBe(4);
    const e = parseEventJson('{"type":"approval_required","approval_id":"a","invocation":{"call_id":"c","name":"Bash"},"subagent":"Verifier 2"}');
    expect(e).toMatchObject({ subagent: "Verifier 2" });
    expect(parseEventJson('{"type":"approval_required","approval_id":"a","invocation":{"call_id":"c","name":"Bash"}}')).toMatchObject({ subagent: null });
  });
});

describe("reducer: question", () => {
  it("blocks the turn until answered and records the answer", () => {
    let s = ev(start(), q);
    expect(phaseOf(s)).toBe("waiting");
    expect(s.question).toBe("Q1");
    s = chatReducer(s, { type: "question_sent", id: "Q1", answer: "a" });
    expect(s.question).toBeNull();
    expect(s.items.find((i) => i.kind === "question")).toMatchObject({ status: "answered", answer: "a" });
    expect(phaseOf(s)).toBe("thinking");
  });
  it("expires locally and closes when the turn ends", () => {
    const s = chatReducer(ev(start(), q), { type: "question_expired", id: "Q1" });
    expect(s.items.find((i) => i.kind === "question")).toMatchObject({ status: "expired" });
    const ended = ev(ev(start(), q), { type: "done", stop_reason: "cancelled" });
    expect(ended.items.find((i) => i.kind === "question")).toMatchObject({ status: "closed" });
    expect(ended.question).toBeNull();
  });
  it("ignores a late expiry for a question that was already answered", () => {
    let s = chatReducer(ev(start(), q), { type: "question_sent", id: "Q1", answer: "a" });
    s = chatReducer(s, { type: "question_expired", id: "Q1" });
    expect(s.items.find((i) => i.kind === "question")).toMatchObject({ status: "answered" });
  });
});

describe("reducer: subagents", () => {
  it("tracks status, steps and finish detail", () => {
    let s = ev(start(), sub("Explore 1", "queued"));
    expect(s.items.at(-1)).toMatchObject({ kind: "subagent", status: "queued" });
    s = ev(s, sub("Explore 1", "started"));
    s = ev(s, sub("Explore 1", "step", "Read"));
    s = ev(s, sub("Explore 1", "step", "Grep"));
    expect(s.items.filter((i) => i.kind === "subagent")).toHaveLength(1);
    expect(s.items.at(-1)).toMatchObject({ status: "running", steps: ["Read", "Grep"], stepCount: 2 });
    s = ev(s, sub("Explore 1", "finished", "error"));
    expect(s.items.at(-1)).toMatchObject({ status: "error" });
  });
  it("keeps only the last steps but counts all", () => {
    let s = ev(start(), sub("Explore 1", "started"));
    for (let i = 0; i < 100; i++) s = ev(s, sub("Explore 1", "step", `T${i}`));
    const it = s.items.at(-1);
    expect(it).toMatchObject({ stepCount: 100 });
    expect(it && it.kind === "subagent" && it.steps.length).toBe(40);
  });
  it("marks unfinished subagents cancelled when the turn ends", () => {
    const s = ev(ev(start(), sub("Explore 1", "started")), { type: "done", stop_reason: "cancelled" });
    expect(s.items.find((i) => i.kind === "subagent")).toMatchObject({ status: "cancelled" });
  });
  it("stores the subagent on the approval", () => {
    const inv = { call_id: "c", name: "Bash", arguments: { command: "ls" } };
    const s = ev(start(), { type: "approval_required", approval_id: "a", invocation: inv, diff: null, verdict: null, subagent: "Verifier 2" });
    expect(s.approval?.subagent).toBe("Verifier 2");
  });
});

describe("reducer: compaction, plan, taint", () => {
  it("adds a compaction divider item", () => {
    const s = ev(start(), { type: "compaction", tokens_before: 12100, tokens_after: 4300, stages: ["summary"] });
    expect(s.items.at(-1)).toMatchObject({ kind: "compaction", before: 12100, after: 4300 });
  });
  it("shows an approved ExitPlanMode plan as a plan item, not a rejected one", () => {
    const inv = { call_id: "p", name: "ExitPlanMode", arguments: { plan: "## Plan\n1. x" } };
    const res = (is_error: boolean): StreamEvent => ({ type: "tool_result", result: { call_id: "p", output: "ok", is_error, tainted: false, spill_path: null } });
    const base = ev(start(), { type: "tool_call", invocation: inv });
    expect(ev(base, res(false)).items.at(-1)).toMatchObject({ kind: "plan", text: "## Plan\n1. x" });
    expect(ev(base, res(true)).items.some((i) => i.kind === "plan")).toBe(false);
  });
  it("keeps the tainted flag on tool results", () => {
    const inv = { call_id: "w", name: "WebFetch", arguments: {} };
    const s = ev(ev(start(), { type: "tool_call", invocation: inv }), { type: "tool_result", result: { call_id: "w", output: "x", is_error: false, tainted: true, spill_path: null } });
    expect(s.items.find((i) => i.kind === "tool")).toMatchObject({ tainted: true });
  });
});

describe("history", () => {
  it("rebuilds plan and summary rows and taint", () => {
    const items = itemsFromMessages([
      { seq: 1, role: "user", content: "hi" },
      { seq: 2, role: "summary", content: "short summary" },
      { seq: 3, role: "plan", content: "## Plan" },
      { seq: 4, role: "assistant", content: "", tool_calls: [{ id: "c1", function: { name: "WebFetch", arguments: "{}" } }] },
      { seq: 5, role: "tool", content: "page", tool_call_id: "c1", tainted: true },
    ]);
    expect(items.map((i) => i.kind)).toEqual(["user", "compaction", "plan", "tool"]);
    expect(items[1]).toMatchObject({ summary: "short summary" });
    expect(items[3]).toMatchObject({ tainted: true, output: "page" });
  });
});

describe("cron", () => {
  const f = (s: string): CronFields => {
    const r = parseCron(s);
    if (!r.ok) throw new Error(r.error);
    return r.fields;
  };
  it("describes common schedules", () => {
    expect(describeCron(f("*/15 * * * *"))).toBe("Every 15 minutes");
    expect(describeCron(f("30 3 * * *"))).toBe("At 03:30, every day");
    expect(describeCron(f("0 9 * * mon-fri"))).toBe("At 09:00 on Mon-Fri");
    expect(describeCron(f("@hourly"))).toBe("Every hour, on the hour");
    expect(describeCron(f("0 0 1 jan,jul *"))).toBe("At 00:00 on day 1 of the month in Jan, Jul");
    expect(describeCron(f("0 8 * * 7"))).toBe("At 08:00 on Sun");
  });
  it("rejects bad input with a reason", () => {
    for (const bad of ["", "* * * *", "* * * * * *", "99 * * * *", "*/0 * * * *", "a b c d e", "5-1 * * * *", "1,,2 * * * *", "* * 0 * *"]) {
      expect(parseCron(bad).ok, bad).toBe(false);
    }
    expect(parseCron("61 * * * *")).toEqual({ ok: false, error: "minute: must be 0-59" });
  });
  it("computes the next run and gives up on impossible dates", () => {
    const from = new Date(2026, 10, 20, 10, 7);
    expect(nextRun(f("*/15 * * * *"), from)).toEqual(new Date(2026, 10, 20, 10, 15));
    expect(nextRun(f("0 9 * * *"), from)).toEqual(new Date(2026, 10, 21, 9, 0));
    expect(nextRun(f("0 0 31 2 *"), from)).toBeNull();
    // dom and dow are ORed when both are restricted
    expect(nextRun(f("0 0 1 * fri"), from)).toEqual(new Date(2026, 10, 27, 0, 0));
  });
});
