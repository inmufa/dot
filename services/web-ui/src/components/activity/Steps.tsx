"use client";
import { Entry } from "@/components/ui";
import type { Item } from "@/lib/stream/reducer";
import { ToolRow } from "./ToolRow";

type Tool = Extract<Item, { kind: "tool" }>;

/** "0.4s", "12s", "2m 3s". */
export function duration(ms: number | undefined): string | null {
  if (ms === undefined || ms < 0) return null;
  if (ms < 10_000) return `${(ms / 1000).toFixed(1)}s`;
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

const STATE = { running: "thinking", awaiting: "waiting", done: undefined, error: undefined } as const;

/** One tool call as a logbook line on the rail. The node carries the status. */
export function ToolStep({ tool, i = 0, time, n }: { tool: Tool; i?: number; time?: React.ReactNode; n?: number }) {
  const ms = tool.at !== undefined && tool.endedAt !== undefined ? tool.endedAt - tool.at : undefined;
  return (
    <Entry time={n !== undefined ? String(n).padStart(2, "0") : time} i={i} state={STATE[tool.status]} className={`e-step s-${tool.status}`}>
      <ToolRow tool={tool} ms={duration(ms)} />
    </Entry>
  );
}
