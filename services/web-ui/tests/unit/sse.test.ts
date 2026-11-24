import { describe, expect, it } from "vitest";
import { parseEventJson } from "@/lib/stream/events";
import { SseParser, readSse } from "@/lib/stream/sse";

describe("SseParser", () => {
  it("emits one payload per frame", () => {
    const p = new SseParser();
    expect(p.feed('data: {"a":1}\n\ndata: {"b":2}\n\n')).toEqual(['{"a":1}', '{"b":2}']);
  });
  it("handles frames split across chunks and CRLF", () => {
    const p = new SseParser();
    expect(p.feed('data: {"a"')).toEqual([]);
    expect(p.feed(':1}\r\n\r')).toEqual([]);
    expect(p.feed("\ndata: x\r\n\r\n")).toEqual(['{"a":1}', "x"]);
  });
  it("joins multi-line data, skips comments and other fields", () => {
    const p = new SseParser();
    expect(p.feed(": ping\nevent: x\nid: 4\ndata: a\ndata: b\n\n")).toEqual(["a\nb"]);
  });
  it("flushes an unterminated final frame", () => {
    const p = new SseParser();
    p.feed("data: tail");
    expect(p.end()).toEqual(["tail"]);
  });
  it("keeps multi-byte characters split across byte chunks", async () => {
    const bytes = new TextEncoder().encode('data: {"t":"Oʻzbek привет 🙂"}\n\n');
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        for (let i = 0; i < bytes.length; i += 3) c.enqueue(bytes.slice(i, i + 3));
        c.close();
      },
    });
    const out: string[] = [];
    for await (const d of readSse(body)) out.push(d);
    expect(JSON.parse(out[0] ?? "{}")).toEqual({ t: "Oʻzbek привет 🙂" });
  });
});

describe("parseEventJson", () => {
  it("parses each contract event", () => {
    expect(parseEventJson('{"type":"token","text":"hi","thinking":true}')).toEqual({ type: "token", text: "hi", thinking: true });
    expect(parseEventJson('{"type":"usage","context_tokens":5,"context_limit":10}')).toEqual({ type: "usage", context_tokens: 5, context_limit: 10 });
    expect(parseEventJson('{"type":"done","stop_reason":"cancelled"}')).toEqual({ type: "done", stop_reason: "cancelled" });
    expect(parseEventJson('{"type":"error","code":4000,"message":"llm"}')).toEqual({ type: "error", code: 4000, message: "llm" });
    const ap = parseEventJson('{"type":"approval_required","approval_id":"a1","invocation":{"call_id":"c","name":"Edit","arguments":{}},"diff":"- a\\n+ b","verdict":{"decision":"ask","stage":"B","reason":"r"}}');
    expect(ap).toMatchObject({ type: "approval_required", approval_id: "a1", diff: "- a\n+ b", verdict: { decision: "ask" } });
  });
  it("rejects malformed or unknown events", () => {
    expect(parseEventJson("not json")).toBeNull();
    expect(parseEventJson('{"type":"nope"}')).toBeNull();
    expect(parseEventJson('{"type":"tool_call","invocation":{"name":"x"}}')).toBeNull();
    expect(parseEventJson('{"type":"approval_required","invocation":{"call_id":"c","name":"n"}}')).toBeNull();
  });
});
