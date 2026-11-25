import { describe, expect, it } from "vitest";
import { effectiveEffort, hasUltrathink, parseEffortArg, splitUltrathink } from "@/lib/effort/levels";
import { MODE_META } from "@/lib/modes/meta";
import { BUILTIN_COMMANDS } from "@/lib/commands/registry";
import { LOCAL_COMMANDS } from "@/lib/commands/runner";

describe("effort", () => {
  it("ultrathink raises one turn to max, voice forces instant", () => {
    expect(effectiveEffort("low", "please ULTRATHINK about it")).toBe("max");
    expect(effectiveEffort("high", "plain")).toBe("high");
    expect(effectiveEffort("max", "x", true)).toBe("off");
    expect(hasUltrathink("ultrathinking")).toBe(false);
  });
  it("parses /effort arguments", () => {
    expect(parseEffortArg("instant")).toBe("off");
    expect(parseEffortArg("Normal")).toBe("medium");
    expect(parseEffortArg("5")).toBe("max");
    expect(parseEffortArg("bogus")).toBeNull();
  });
  it("splits the keyword for the shimmer overlay", () => {
    expect(splitUltrathink("a ultrathink b")).toEqual([{ text: "a ", hot: false }, { text: "ultrathink", hot: true }, { text: " b", hot: false }]);
    expect(splitUltrathink("")).toEqual([]);
  });
});

describe("modes and commands", () => {
  it("every mode has a label and description", () => {
    for (const m of ["plan", "default", "acceptEdits", "auto", "bypass"] as const) expect(MODE_META[m].label).toBeTruthy();
  });
  it("every local runner is a registered command", () => {
    const names = new Set(BUILTIN_COMMANDS.map((c) => c.name));
    expect(LOCAL_COMMANDS.filter((n) => !names.has(n))).toEqual([]);
  });
});
