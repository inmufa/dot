import { describe, expect, it } from "vitest";
import { place } from "@/components/ui/position";

const rect = (top: number, left: number, w = 40, h = 32) => ({ top, left, right: left + w, bottom: top + h, width: w, height: h });

describe("place", () => {
  it("opens below when there is room", () => {
    expect(place(rect(100, 100), { width: 200, height: 150 }, 1000, 800, { side: "auto", align: "start" }).side).toBe("bottom");
  });
  it("flips up near the bottom edge", () => {
    const p = place(rect(700, 100), { width: 200, height: 300 }, 1000, 800, { side: "bottom", align: "start" });
    expect(p.side).toBe("top");
    expect(p.top).toBeLessThan(700);
  });
  it("clamps into the viewport and flips align", () => {
    const p = place(rect(100, 380), { width: 200, height: 100 }, 400, 800, { side: "auto", align: "start" });
    expect(p.left + 200).toBeLessThanOrEqual(392);
    expect(p.align).toBe("end");
  });
});
