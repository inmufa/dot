import type { ReactNode } from "react";
import { Bullet } from "./Bullet";
import { StateDot } from "./StateDot";
import type { DotPhase } from "@/lib/stream/reducer";

interface Props {
  /** Mono record in the gutter: clock time or step number. */
  time?: ReactNode;
  /** Live state shows the animated dot on the rail; omit for a static node. */
  state?: DotPhase;
  children: ReactNode;
  /** Stagger index for the node-in motion. */
  i?: number;
  className?: string;
}

/** One log entry: time in the gutter, a rail node, content right. Consecutive entries share one rail. */
export function Entry({ time, state, children, i = 0, className }: Props) {
  return (
    <div className={`entry${className ? ` ${className}` : ""}`} style={{ ["--i" as string]: i }}>
      <span className="entry-time rec">{time}</span>
      <span className="entry-node anim-node">{state ? <StateDot state={state} /> : <Bullet />}</span>
      <div className="entry-body">{children}</div>
    </div>
  );
}
