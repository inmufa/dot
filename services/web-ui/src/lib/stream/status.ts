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

export interface LiveStatus { label: string; kind: "start" | "think" | "tool" | "compose" | "review" | "you" | "plan" }

/**
 * The one-line "what is Dot doing" status, or null when the answer text itself is streaming.
 * `quiet` is true when nothing new has arrived for a moment (a long tool call streams no visible text).
 */
export function liveStatus(items: Item[], o: { running: boolean; planning: boolean; approval: boolean; question: boolean; quiet: boolean }): LiveStatus | null {
  if (!o.running) return null;
  if (o.approval) return { label: "Waiting for your OK", kind: "you" };
  if (o.question) return { label: "Waiting for your answer", kind: "you" };
  const tool = [...items].reverse().find((i): i is Tool => i.kind === "tool" && (i.status === "running" || i.status === "awaiting"));
  if (tool) return { label: toolStatus(tool), kind: "tool" };
  if (o.planning) return { label: "Drafting a research plan", kind: "plan" };
  const last = items[items.length - 1];
  if (!last || last.kind === "user") return { label: "Getting started", kind: "start" };
  if (last.kind === "assistant" && last.streaming && !last.text) return { label: "Thinking", kind: "think" };
  if (last.kind === "assistant" && last.streaming) return o.quiet ? { label: "Preparing the next step", kind: "compose" } : null;
  if (last.kind === "tool") return { label: "Going through the results", kind: "review" };
  if (last.kind === "compaction") return { label: "Tidying up the context", kind: "review" };
  return { label: o.quiet ? "Preparing the next step" : "Thinking", kind: o.quiet ? "compose" : "think" };
}
