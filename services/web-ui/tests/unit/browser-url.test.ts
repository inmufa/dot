import { describe, expect, it } from "vitest";
import { fitViewport, normalizeUrl } from "@/lib/api/browser";

describe("normalizeUrl", () => {
  it("adds https to bare hosts and keeps explicit schemes", () => {
    expect(normalizeUrl(" example.com/a ")).toBe("https://example.com/a");
    expect(normalizeUrl("http://example.com")).toBe("http://example.com");
  });
});

describe("fitViewport", () => {
  it("floors the panel size and clamps it to the worker bounds", () => {
    expect(fitViewport(536.7, 700.2)).toEqual({ width: 536, height: 700 });
    expect(fitViewport(200, 100)).toEqual({ width: 320, height: 320 });
    expect(fitViewport(4000, 3000)).toEqual({ width: 1920, height: 1600 });
  });
});
