import { describe, expect, it } from "vitest";
import { checkRequest, resolveBackend, safeUpstreamPath } from "@/lib/server/guard";
import { filterCommands, mergeCommands, parseCommandLine, slashQuery } from "@/lib/commands/registry";
import { parseBlocks, parseInline } from "@/lib/util/markdown";

const base = { method: "POST", host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000", fetchSite: "same-origin", extraHosts: [] };

describe("proxy guard", () => {
  it("allows only v1, ready and health paths", () => {
    expect(safeUpstreamPath(["v1", "sessions", "S1", "chat"])).toBe("v1/sessions/S1/chat");
    expect(safeUpstreamPath(["ready"])).toBe("ready");
    expect(safeUpstreamPath(["v1", "..", "etc"])).toBeNull();
    expect(safeUpstreamPath(["admin"])).toBeNull();
    expect(safeUpstreamPath(["v1", "a/b"])).toBeNull();
  });
  it("rejects cross-origin writes and foreign hosts", () => {
    expect(checkRequest(base)).toBeNull();
    expect(checkRequest({ ...base, origin: "http://evil.test" })).toBe("cross_origin");
    expect(checkRequest({ ...base, origin: null })).toBe("origin_required");
    expect(checkRequest({ ...base, fetchSite: "cross-site" })).toBe("cross_site");
    expect(checkRequest({ ...base, host: "evil.test" })).toBe("host_not_allowed");
    expect(checkRequest({ ...base, method: "GET", origin: null, fetchSite: null })).toBeNull();
    expect(checkRequest({ ...base, host: "dot.lan:3000", origin: "http://dot.lan:3000", extraHosts: ["dot.lan:3000"] })).toBeNull();
  });
  it("accepts only loopback backends by default", () => {
    expect(resolveBackend(undefined, false)?.host).toBe("127.0.0.1:8000");
    expect(resolveBackend("http://10.0.0.5:8000", false)).toBeNull();
    expect(resolveBackend("http://backend:8000", true)?.hostname).toBe("backend");
    expect(resolveBackend("file:///etc", true)).toBeNull();
  });
});

describe("slash", () => {
  it("merges builtins, remote registry and skills", () => {
    const items = mergeCommands(null, [{ name: "review", description: "d", source: "bundled", available: true, reason: null, model_invocable: true }, { name: "mode", description: "dup", source: "user", available: true, reason: null, model_invocable: true }]);
    expect(items.find((i) => i.name === "mode")?.kind).toBe("command");
    expect(items.find((i) => i.name === "review")?.kind).toBe("skill");
    expect(["compact", "clear", "effort", "model", "context", "plan", "research", "resume", "rename", "export", "memory", "mcp", "skills", "tasks", "retry", "branch", "rewind", "mode", "stop", "new", "help"].filter((n) => !items.some((i) => i.name === n))).toEqual([]);
    expect(mergeCommands([{ name: "mode", args: null, description: "remote", group: "core", available: false, reason: "x" }], []).find((i) => i.name === "mode")).toMatchObject({ description: "remote", available: false });
    expect(slashQuery("/re")).toBe("re");
    expect(slashQuery("/re x")).toBeNull();
    expect(slashQuery("hi /x")).toBeNull();
    expect(filterCommands(items, "rew")[0]?.name).toBe("rewind");
    expect(parseCommandLine("/mode plan")).toEqual({ name: "mode", arg: "plan" });
    expect(parseCommandLine("hello")).toBeNull();
  });
});

describe("markdown", () => {
  it("parses blocks and marks unclosed fences", () => {
    const b = parseBlocks("# T\n\ntext **b** `c`\n\n```py\nx = 1");
    expect(b.map((x) => x.t)).toEqual(["h", "p", "code"]);
    expect(b[2]).toMatchObject({ lang: "py", closed: false });
  });
  it("never emits unsafe links", () => {
    const i = parseInline("[x](javascript:alert(1)) and [ok](https://a.b)");
    expect(i.some((n) => n.t === "link" && n.href.startsWith("javascript"))).toBe(false);
    expect(i.some((n) => n.t === "link" && n.href === "https://a.b")).toBe(true);
  });
  it("parses lists and tables, and survives pathological input", () => {
    expect(parseBlocks("- a\n- b\n\n1. x")[0]).toMatchObject({ t: "list", items: [expect.anything(), expect.anything()] });
    expect(parseBlocks("| a | b |\n|---|--:|\n| 1 | 2 |")[0]).toMatchObject({ t: "table" });
    const t0 = Date.now();
    parseBlocks("**".repeat(20_000) + "\n" + "_a ".repeat(10_000) + "\n" + "[".repeat(5000));
    expect(Date.now() - t0).toBeLessThan(2000);
  });
});
