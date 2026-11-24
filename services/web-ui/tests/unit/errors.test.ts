import { describe, expect, it } from "vitest";
import { describeError, parseEnvelope } from "@/lib/api/errors";

const env = (code: number, msg: string, show = true) => [{ key: null, code, show, icon_type: "error", type: "domain_error", messages: [msg] }];

describe("error envelope", () => {
  it("parses a list envelope and drops junk", () => {
    expect(parseEnvelope(env(2001, "busy"))).toHaveLength(1);
    expect(parseEnvelope({ error: "x" })).toEqual([]);
    expect(parseEnvelope([null, 3, { code: "x" }])).toEqual([]);
  });
  it("prefers the localised server text and adds a hint", () => {
    const i = describeError(409, env(2001, "Сессия занята"));
    expect(i).toMatchObject({ kind: "busy", code: 2001, title: "Сессия занята", retryable: true });
    expect(i.hint).toMatch(/Stop/);
  });
  it("falls back to local text when show is false", () => {
    expect(describeError(500, env(1000, "secret", false)).title).toBe("Something went wrong on the backend.");
  });
  it("classifies network, auth and not-found", () => {
    expect(describeError(0, null).kind).toBe("offline");
    expect(describeError(502, null).kind).toBe("offline");
    expect(describeError(401, null)).toMatchObject({ kind: "unauthorized", retryable: false });
    expect(describeError(404, env(2000, "nope")).kind).toBe("notfound");
    expect(describeError(503, env(1008, "dep")).hint).toMatch(/dependency/);
  });
});
