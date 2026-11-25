import { describe, expect, it } from "vitest";
import { artifactMessage, parseArtifactEvent } from "@/components/canvas/artifact";
import { fileContentPath, toFileEntries } from "@/lib/api/files";

describe("artifact events", () => {
  it("accepts only the reporter's messages", () => {
    expect(parseArtifactEvent({ dotArtifact: 1, kind: "error", message: "boom" })).toEqual({ kind: "error", message: "boom" });
    expect(parseArtifactEvent({ dotArtifact: 1, kind: "warn", message: "w" })?.kind).toBe("warn");
    expect(parseArtifactEvent({ probe: {} })).toBeNull();
    expect(parseArtifactEvent("x")).toBeNull();
    expect(parseArtifactEvent({ dotArtifact: 1, kind: "error" })).toBeNull();
  });
  it("builds the Fix with Dot message", () => {
    const m = artifactMessage("a.html", [{ kind: "error", message: "x is not defined" }], " add a legend ");
    expect(m).toContain("a.html");
    expect(m).toContain("- error: x is not defined");
    expect(m).toContain("What I want changed: add a legend");
    expect(m).toContain("cannot use the network");
  });
});

describe("files api shape", () => {
  it("maps the backend FileInfo", () => {
    const [f] = toFileEntries([{ path: "/w/a.html", size: 5, modified_at: "2026-01-01T00:00:00Z" }]);
    expect(f).toEqual({ path: "/w/a.html", size: 5, mtime: "2026-01-01T00:00:00Z", kind: "html" });
  });
  it("uses the real content route and asks for render only when told", () => {
    expect(fileContentPath("/w/a b.html")).toBe("/v1/files/content?path=%2Fw%2Fa%20b.html");
    expect(fileContentPath("/w/a.html", true)).toContain("&render=1");
  });
});
