"use client";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Badge, Button } from "@/components/ui";
import { shortArgs } from "@/lib/util/format";
import type { Item } from "@/lib/stream/reducer";

type Tool = Extract<Item, { kind: "tool" }>;
const LIMIT = 4000;

function prettyArgs(args: Record<string, unknown>): string {
  const cmd = args.command;
  if (typeof cmd === "string" && Object.keys(args).length === 1) return cmd;
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return "";
  }
}

const STATUS_TEXT = { running: "running", awaiting: "needs approval", done: "done", error: "failed" } as const;
const SHOWN = { running: "", awaiting: "needs approval", done: "", error: "failed" } as const;

/** Logbook line: name, mono args, duration. Status is the rail node of the entry around it. */
export function ToolRow({ tool, ms }: { tool: Tool; ms?: string | null }) {
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState(false);
  const out = tool.output ?? "";
  const cut = !all && out.length > LIMIT;
  return (
    <div className="tool" data-status={tool.status}>
      <button type="button" className="tool-row" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="tool-name">{tool.name}</span>
        {tool.tainted && <span className="sr-only">untrusted content</span>}
        <span className="tool-args" title={shortArgs(tool.args, 400)}>{shortArgs(tool.args)}</span>
        {SHOWN[tool.status] && <span className="tool-st rec">{SHOWN[tool.status]}</span>}
        {ms && <span className="tool-ms rec">{ms}</span>}
        <ChevronRight size={14} aria-hidden className="chev" />
        <span className="sr-only">{STATUS_TEXT[tool.status]}</span>
      </button>
      {open && (
        <div className="tool-detail anim-fade">
          <div className="tool-label">Arguments</div>
          <pre className="tool-pre">{prettyArgs(tool.args)}</pre>
          <div className="tool-label">
            Result {tool.tainted && <Badge tone="warn">untrusted content</Badge>}
          </div>
          {tool.output === undefined ? (
            <p className="muted">{tool.status === "awaiting" ? "Waiting for your decision." : "No result yet."}</p>
          ) : out === "" ? (
            <p className="muted">Empty output.</p>
          ) : (
            <>
              <pre className="tool-pre" data-error={tool.status === "error"} tabIndex={0}>{cut ? out.slice(0, LIMIT) : out}</pre>
              {cut && (
                <Button size="sm" onClick={() => setAll(true)}>
                  Show all ({out.length.toLocaleString("en")} chars)
                </Button>
              )}
              {tool.spillPath && <p className="muted">Full output on the workspace: <code>{tool.spillPath}</code></p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
