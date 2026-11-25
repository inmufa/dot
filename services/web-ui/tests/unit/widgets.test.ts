import { describe, expect, it } from "vitest";
import { PARSERS, isWidgetKind } from "@/components/widgets/schema";
import { parseFields } from "@/components/widgets/fields";

const OK: Record<string, unknown> = {
  table: { columns: [{ key: "a", label: "A", type: "number" }], rows: [{ a: 1 }, { a: null }], caption: "c" },
  chart: { type: "line", series: [{ name: "s", points: [{ x: "a", y: 1 }, { x: 2, y: 3 }] }] },
  stats: { items: [{ label: "x", value: 5, delta: 1.2 }] },
  steps: { items: [{ title: "t", status: "done" }] },
  checklist: { items: [{ text: "t", done: true }] },
  cards: { items: [{ title: "t", meta: [{ label: "l", value: "v" }] }] },
  callout: { level: "info", body: "b" },
  tabs: { tabs: [{ label: "l", body: "b" }] },
  accordion: { items: [{ title: "t", body: "b" }] },
  choices: { options: ["a", "b"] },
};
const rows = (n: number) => Array.from({ length: n }, (_, i) => ({ a: i }));

describe("widget schema", () => {
  it("accepts valid props for every kind", () => {
    for (const [k, v] of Object.entries(OK)) expect(PARSERS[k as keyof typeof PARSERS](v), k).not.toBeNull();
  });
  it("rejects non-objects, nulls and wrong shapes", () => {
    for (const k of Object.keys(PARSERS))
      for (const bad of [null, undefined, 5, "x", [], { items: "nope" }, { columns: "oops", rows: 1 }])
        expect(PARSERS[k as keyof typeof PARSERS](bad), `${k} ${JSON.stringify(bad)}`).toBeNull();
  });
  it("enforces caps", () => {
    const cols = [{ key: "a", label: "A" }];
    expect(PARSERS.table({ columns: cols, rows: rows(201) })).toBeNull();
    expect(PARSERS.table({ columns: Array.from({ length: 13 }, (_, i) => ({ key: `k${i}`, label: "x" })), rows: [] })).toBeNull();
    expect(PARSERS.callout({ level: "info", body: "A".repeat(2001) })).toBeNull();
    expect(PARSERS.cards({ items: Array.from({ length: 31 }, () => ({ title: "t" })) })).toBeNull();
    const pts = (n: number) => Array.from({ length: n }, (_, i) => ({ x: i, y: i }));
    expect(PARSERS.chart({ type: "bar", series: [{ name: "s", points: pts(201) }] })).toBeNull();
    expect(PARSERS.chart({ type: "bar", series: Array.from({ length: 9 }, () => ({ name: "s", points: pts(2) })) })).toBeNull();
  });
  it("rejects hostile chart payloads", () => {
    expect(PARSERS.chart({ type: "radar", series: [{ name: "s", points: [{ x: 1, y: 1 }] }] })).toBeNull();
    expect(PARSERS.chart({ type: "line", series: [{ name: "b", points: [{ x: "a", y: "not a number" }] }] })).toBeNull();
    expect(PARSERS.chart({ type: "line", series: [{ name: "b", points: [{ y: 3 }] }] })).toBeNull();
    expect(PARSERS.steps({ items: [{ title: "ok", status: "weird" }] })).toBeNull();
    expect(PARSERS.choices({ options: [1, null, "x"] })).toBeNull();
  });
  it("knows its kinds and ignores prototype keys", () => {
    expect(isWidgetKind("table")).toBe(true);
    expect(isWidgetKind("hologram")).toBe(false);
    expect(isWidgetKind("constructor")).toBe(false);
    expect(isWidgetKind("__proto__")).toBe(false);
  });
  it("keeps markup as inert strings", () => {
    const r = PARSERS.callout({ level: "danger", body: "<script>alert(1)</script>" });
    expect(r?.body).toBe("<script>alert(1)</script>");
  });
});

describe("form fields", () => {
  it("parses select and multi select fields", () => {
    const f = parseFields([{ id: "a", type: "multi_select", label: "L", options: [{ label: "x" }, { label: "y" }] }, { id: "b", type: "text", label: "T" }]);
    expect(f?.map((x) => x.type)).toEqual(["multi_select", "text"]);
  });
  it("drops garbage", () => {
    expect(parseFields("nope")).toBeNull();
    expect(parseFields([{ id: "a", type: "evil", label: "L" }])).toBeNull();
  });
});
