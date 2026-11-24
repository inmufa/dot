import { describe, expect, it } from "vitest";
import { parseDiff } from "@/lib/diff";

describe("parseDiff", () => {
  it("parses unified diffs with line numbers", () => {
    const d = parseDiff("--- a/x\n+++ b/x\n@@ -10,3 +10,4 @@\n ctx\n-old\n+new1\n+new2\n ctx2\n");
    expect(d.added).toBe(2);
    expect(d.removed).toBe(1);
    expect(d.lines.map((l) => l.kind)).toEqual(["meta", "meta", "hunk", "ctx", "del", "add", "add", "ctx"]);
    expect(d.lines[3]).toMatchObject({ oldNo: 10, newNo: 10 });
    expect(d.lines[4]).toMatchObject({ oldNo: 11, newNo: null });
    expect(d.lines[6]).toMatchObject({ newNo: 12 });
  });
  it("parses the simple Edit format", () => {
    const d = parseDiff("- old line\n+ new line");
    expect(d.lines[0]).toMatchObject({ kind: "del", text: " old line", oldNo: null });
    expect(d.added).toBe(1);
  });
  it("treats new files (/dev/null) as all additions", () => {
    const d = parseDiff("--- /dev/null\n+++ b/n.py\n@@ -0,0 +1,2 @@\n+a\n+b");
    expect(d.added).toBe(2);
    expect(d.removed).toBe(0);
  });
  it("copes with huge and empty input", () => {
    expect(parseDiff("").lines.length).toBe(1);
    const big = Array.from({ length: 50_000 }, (_, i) => `+line ${i}`).join("\n");
    expect(parseDiff(big).added).toBe(50_000);
  });
});
