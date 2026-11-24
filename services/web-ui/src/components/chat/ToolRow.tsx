"use client";
import { AlertCircle, Check, ChevronRight, LoaderCircle, ShieldAlert, ShieldQuestion } from "lucide-react";
import { useState } from "react";
import { shortArgs } from "@/lib/format";
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

export function ToolRow({ tool }: { tool: Tool }) {
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState(false);
  const out = tool.output ?? "";
  const cut = !all && out.length > LIMIT;
  const Icon = tool.status === "done" ? Check : tool.status === "error" ? AlertCircle : tool.status === "awaiting" ? ShieldQuestion : LoaderCircle;
  return (
    <div className="tool" data-status={tool.status}>
      <button type="button" className="tool-row" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChevronRight size={14} aria-hidden className="chev" />
        <Icon size={14} aria-hidden className={tool.status === "running" ? "spin tool-ico" : "tool-ico"} />
        <span className="tool-name">{tool.name}</span>
        {tool.tainted && (
          <span className="taint" title="Untrusted content">
            <ShieldAlert size={14} aria-hidden />
            <span className="sr-only">untrusted content</span>
          </span>
        )}
        <span className="tool-args">{shortArgs(tool.args)}</span>
        <span className="sr-only">{STATUS_TEXT[tool.status]}</span>
      </button>
      {open && (
        <div className="tool-detail">
          <div className="tool-label">Arguments</div>
          <pre className="tool-pre">{prettyArgs(tool.args)}</pre>
          <div className="tool-label">
            Result {tool.tainted && <span className="badge" data-tone="warn">untrusted content</span>}
          </div>
          {tool.output === undefined ? (
            <p className="muted">{tool.status === "awaiting" ? "Waiting for your decision." : "No result yet."}</p>
          ) : out === "" ? (
            <p className="muted">Empty output.</p>
          ) : (
            <>
              <pre className="tool-pre" data-error={tool.status === "error"} tabIndex={0}>{cut ? out.slice(0, LIMIT) : out}</pre>
              {cut && (
                <button type="button" className="btn btn-sm" onClick={() => setAll(true)}>
                  Show all ({out.length.toLocaleString("en")} chars)
                </button>
              )}
              {tool.spillPath && <p className="muted">Full output on the workspace: <code>{tool.spillPath}</code></p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
