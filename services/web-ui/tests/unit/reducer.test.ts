import { describe, expect, it } from "vitest";
import type { StreamEvent } from "@/lib/stream/events";
import { itemsFromMessages } from "@/lib/stream/history";
import { chatReducer, initialChat, phaseOf, type ChatState } from "@/lib/stream/reducer";

const ev = (s: ChatState, e: StreamEvent): ChatState => chatReducer(s, { type: "event", event: e, now: 1 });
const inv = { call_id: "c1", name: "Edit", arguments: { file_path: "a.py" } };

describe("chat reducer", () => {
  it("streams thinking and text into one assistant item", () => {
    let s = chatReducer(initialChat, { type: "send", text: "hi" });
    expect(phaseOf(s)).toBe("thinking");
    s = ev(s, { type: "token", text: "hm", thinking: true });
    s = ev(s, { type: "token", text: "Hel", thinking: false });
    s = ev(s, { type: "token", text: "lo", thinking: false });
    const a = s.items[1];
    expect(a).toMatchObject({ kind: "assistant", text: "Hello", thinking: "hm", streaming: true });
  });
  it("runs the approval flow and returns to idle", () => {
    let s = chatReducer(initialChat, { type: "send", text: "edit" });
    s = ev(s, { type: "tool_call", invocation: inv });
    s = ev(s, { type: "approval_required", approval_id: "ap", invocation: inv, diff: "- a\n+ b", verdict: { decision: "ask", stage: "B", reason: "r" }, subagent: null });
    expect(phaseOf(s)).toBe("waiting");
    expect(s.items.find((i) => i.kind === "tool")).toMatchObject({ status: "awaiting" });
    s = chatReducer(s, { type: "approval_sent" });
    expect(s.approval).toBeNull();
    s = ev(s, { type: "tool_result", result: { call_id: "c1", output: "ok", is_error: false, tainted: false, spill_path: null } });
    s = ev(s, { type: "done", stop_reason: "end_turn" });
    expect(phaseOf(s)).toBe("idle");
    expect(s.items.find((i) => i.kind === "tool")).toMatchObject({ status: "done", output: "ok" });
  });
  it("shows denied results as errors and tool_call after tokens opens a new item", () => {
    let s = chatReducer(initialChat, { type: "send", text: "x" });
    s = ev(s, { type: "token", text: "a", thinking: false });
    s = ev(s, { type: "tool_call", invocation: inv });
    s = ev(s, { type: "token", text: "b", thinking: false });
    expect(s.items.map((i) => i.kind)).toEqual(["user", "assistant", "tool", "assistant"]);
    s = ev(s, { type: "tool_result", result: { call_id: "c1", output: "Denied (error 3000)", is_error: true, tainted: false, spill_path: null } });
    expect(s.items[2]).toMatchObject({ status: "error" });
  });
  it("records usage, error and cancelled stop", () => {
    let s = chatReducer(initialChat, { type: "send", text: "x" });
    s = ev(s, { type: "usage", context_tokens: 10, context_limit: 100 });
    s = ev(s, { type: "error", code: 4000, message: "llm down" });
    s = ev(s, { type: "done", stop_reason: "cancelled" });
    expect(s.usage).toEqual({ tokens: 10, limit: 100 });
    expect(s.items.filter((i) => i.kind === "notice")).toHaveLength(2);
    expect(s.running).toBe(false);
  });
  it("ends open tools when the stream dies", () => {
    let s = chatReducer(initialChat, { type: "send", text: "x" });
    s = ev(s, { type: "tool_call", invocation: inv });
    s = chatReducer(s, { type: "end", error: { text: "lost" } });
    expect(s.items.find((i) => i.kind === "tool")).toMatchObject({ status: "error" });
    expect(s.running).toBe(false);
  });
});

describe("itemsFromMessages", () => {
  it("rebuilds tools from both tool_call shapes and skips rewound rows", () => {
    const items = itemsFromMessages([
      { seq: 1, role: "user", content: "go" },
      { seq: 2, role: "assistant", content: "ok", tool_calls: [{ id: "t1", function: { name: "Bash", arguments: '{"command":"ls"}' } }] },
      { seq: 3, role: "tool", content: "a\nb", tool_call_id: "t1" },
      { seq: 4, role: "user", content: "gone", rewound: true },
    ]);
    expect(items.map((i) => i.kind)).toEqual(["user", "assistant", "tool"]);
    expect(items[2]).toMatchObject({ name: "Bash", args: { command: "ls" }, output: "a\nb" });
  });
});

describe("injected message", () => {
  it("moves the queued message into the transcript", () => {
    let s = chatReducer(initialChat, { type: "send", text: "go", now: 1 });
    s = chatReducer(s, { type: "enqueue", id: "q1", text: "also this" });
    s = chatReducer(s, { type: "event", event: { type: "injected", text: "also this" }, now: 2 });
    expect(s.queue).toEqual([]);
    expect(s.items.at(-1)).toMatchObject({ kind: "user", text: "also this" });
    expect(s.running).toBe(true);
  });
});
