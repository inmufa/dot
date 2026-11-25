export type Side = "top" | "bottom";
export type Align = "start" | "end";
export interface Placement { side: Side | "auto"; align: Align }
export interface Rect { top: number; left: number; right: number; bottom: number; width: number; height: number }
export interface Placed { top: number; left: number; side: Side; align: Align; maxHeight: number }

const GAP = 6;
const EDGE = 8;

/** Pure placement: prefers `side`, flips when the other side has more room, clamps into the viewport. */
export function place(anchor: Rect, size: { width: number; height: number }, vw: number, vh: number, want: Placement): Placed {
  const below = vh - anchor.bottom - GAP - EDGE;
  const above = anchor.top - GAP - EDGE;
  let side: Side = want.side === "auto" ? (below >= size.height || below >= above ? "bottom" : "top") : want.side;
  if (side === "bottom" && below < size.height && above > below) side = "top";
  else if (side === "top" && above < size.height && below > above) side = "bottom";
  const maxHeight = Math.max(120, side === "bottom" ? below : above);
  const h = Math.min(size.height, maxHeight);
  const top = side === "bottom" ? anchor.bottom + GAP : anchor.top - GAP - h;
  let align = want.align;
  let left = align === "start" ? anchor.left : anchor.right - size.width;
  const maxLeft = vw - EDGE - size.width;
  if (left > maxLeft) { left = maxLeft; align = "end"; }
  if (left < EDGE) { left = EDGE; align = "start"; }
  return { top, left, side, align, maxHeight };
}
