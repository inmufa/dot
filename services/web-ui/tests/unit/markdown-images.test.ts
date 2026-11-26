import { describe, expect, it } from "vitest";
import { parseBlocks, safeImageSrc } from "@/lib/util/markdown";

describe("markdown images", () => {
  it("makes a single image a one-item gallery", () => {
    const b = parseBlocks("![cat](https://x.io/a.png)");
    expect(b).toEqual([{ t: "gallery", items: [{ src: "https://x.io/a.png", alt: "cat" }] }]);
  });
  it("merges consecutive images into one gallery between text", () => {
    const b = parseBlocks("Before\n![a](https://x.io/1.png)\n![b](out/2.png) ![c](/w/3.jpg)\nAfter");
    expect(b.map((x) => x.t)).toEqual(["p", "gallery", "p"]);
    expect(b[1]).toMatchObject({ items: [{ alt: "a" }, { src: "out/2.png" }, { src: "/w/3.jpg" }] });
  });
  it("rejects dangerous schemes", () => {
    expect(safeImageSrc("javascript:alert(1)")).toBeNull();
    expect(safeImageSrc("data:text/html;base64,AAAA")).toBeNull();
    expect(safeImageSrc("data:image/png;base64,AAAA")).not.toBeNull();
    expect(safeImageSrc("//evil.com/a.png")).toBeNull();
    expect(parseBlocks("![x](javascript:alert(1))")).toEqual([{ t: "p", c: [{ t: "text", v: "x" }] }]);
  });
  it("hides an image cut off while streaming", () => {
    for (const s of ["hi ![al", "hi ![alt]", "hi ![alt](https://x.io/a.p"]) {
      expect(parseBlocks(s)).toEqual([{ t: "p", c: [{ t: "text", v: "hi " }] }]);
    }
  });
});
