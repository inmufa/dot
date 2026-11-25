/** What a rendered page reports to the Preview tab (see backend artifact_runtime.js). */
export interface ArtifactIssue {
  kind: "error" | "warn";
  message: string;
}

export function parseArtifactEvent(data: unknown): ArtifactIssue | null {
  if (typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  if (d.dotArtifact !== 1 || typeof d.message !== "string") return null;
  return { kind: d.kind === "warn" ? "warn" : "error", message: d.message.slice(0, 1000) };
}

/** The message "Fix with Dot" sends back to the agent. */
export function artifactMessage(path: string, issues: ArtifactIssue[], note: string): string {
  const lines = issues.map((i) => `- ${i.kind}: ${i.message}`);
  const parts = [`The interactive page ${path} has a problem.`];
  if (lines.length) parts.push(`Errors and console output from the preview:\n${lines.join("\n")}`);
  if (note.trim()) parts.push(`What I want changed: ${note.trim()}`);
  parts.push("Read the file, fix it, and write the whole file again. The page cannot use the network: embed data instead.");
  return parts.join("\n\n");
}
