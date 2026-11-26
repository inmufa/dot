import type { Item } from "./reducer";

type Tool = Extract<Item, { kind: "tool" }>;

const host = (u: unknown): string => {
  try {
    return new URL(String(u)).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
};
const file = (p: unknown): string => (typeof p === "string" ? (p.split("/").pop() ?? p) : "");

/** What a running tool is doing, in words. */
function toolStatus(t: Tool): string {
  const a = t.args;
  switch (t.name) {
    case "WebSearch": return "Searching the web";
    case "ImageSearch": return "Finding images";
    case "WebFetch": return host(a.url) ? `Reading ${host(a.url)}` : "Reading a page";
    case "Read": return file(a.file_path) ? `Reading ${file(a.file_path)}` : "Reading a file";
    case "Write": return file(a.file_path) ? `Writing ${file(a.file_path)}` : "Writing a file";
    case "Edit": return file(a.file_path) ? `Editing ${file(a.file_path)}` : "Editing a file";
    case "Glob": case "Grep": return "Searching files";
    case "Bash": case "BashOutput": return "Running a command";
    case "KillShell": return "Stopping a command";
    case "Memory": case "MemoryRecall": return "Checking memory";
    case "Agent": return "Handing off to a helper";
    case "Skill": return "Loading a skill";
    case "ToolSearch": return "Looking for the right tool";
    case "Present": return "Building a view";
    default:
      if (t.name.startsWith("Browser")) return host(a.url) ? `Browsing ${host(a.url)}` : "Using the browser";
      return `Using ${t.name}`;
  }
}

export interface LiveStatus { label: string; kind: "start" | "think" | "tool" | "draft" | "review" | "you" | "plan" }

const size = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k chars` : `${n} chars`);

/** What a tool call still being written will do, with its size so far. */
function draftStatus(d: { name: string; target: string; chars: number }): string {
  const t = d.target;
  const big = d.chars > 300 ? ` (${size(d.chars)})` : "";
  switch (d.name) {
    case "Write": return `Writing ${file(t) || "a file"}${big}`;
    case "Edit": return `Editing ${file(t) || "a file"}${big}`;
    case "WebSearch": return t ? `Searching: ${t}` : "Writing a search";
    case "ImageSearch": return t ? `Finding images: ${t}` : "Finding images";
    case "WebFetch": return host(t) ? `Opening ${host(t)}` : "Picking a page to read";
    case "Bash": return t ? `Preparing a command: ${t.slice(0, 60)}` : `Writing a command${big}`;
    case "Present": return `Building a view${big}`;
    case "Agent": return "Briefing a helper";
    default: return `Preparing ${d.name}${big}`;
  }
}

/**
 * The one-line "what is Dot doing" status, or null when the answer text itself is streaming.
 */
export function liveStatus(items: Item[], o: { running: boolean; planning: boolean; approval: boolean; question: boolean; draft: { name: string; target: string; chars: number } | null }): LiveStatus | null {
  if (!o.running) return null;
  if (o.approval) return { label: "Waiting for your OK", kind: "you" };
  if (o.question) return { label: "Waiting for your answer", kind: "you" };
  const tool = [...items].reverse().find((i): i is Tool => i.kind === "tool" && (i.status === "running" || i.status === "awaiting"));
  if (tool) return { label: toolStatus(tool), kind: "tool" };
  if (o.draft) return { label: draftStatus(o.draft), kind: "draft" };
  if (o.planning) return { label: "Drafting a research plan", kind: "plan" };
  const last = items[items.length - 1];
  if (!last || last.kind === "user") return { label: "Getting started", kind: "start" };
  // the live "Thinking 7s" line already says it
  if (last.kind === "assistant" && last.streaming && !last.text) return last.thinking ? null : { label: "Thinking", kind: "think" };
  if (last.kind === "assistant" && last.streaming) return null; // the answer itself is streaming
  if (last.kind === "tool") return { label: "Going through the results", kind: "review" };
  if (last.kind === "compaction") return { label: "Tidying up the context", kind: "review" };
  return { label: "Thinking", kind: "think" };
}
