import { StateDot } from "@/components/ui";

/** Gutter word and accent node of a pending decision, so it sits on the rail like any other entry. */
export function PendRail() {
  return (
    <>
      <span className="pend-time rec">needs your call</span>
      <span className="pend-node anim-node"><StateDot state="waiting" /></span>
    </>
  );
}
