import type { DotPhase } from "@/lib/stream/reducer";

const LABEL: Record<DotPhase, string> = { idle: "Idle", thinking: "Thinking", waiting: "Needs approval" };

/** Decorative by default (pair with visible text); pass `labelled` when it stands alone. */
export function StateDot({ state, large, labelled }: { state: DotPhase; large?: boolean; labelled?: boolean }) {
  return (
    <span
      className={large ? "dot dot-lg" : "dot"}
      data-state={state}
      role={labelled ? "img" : undefined}
      aria-label={labelled ? LABEL[state] : undefined}
      aria-hidden={labelled ? undefined : true}
    />
  );
}
