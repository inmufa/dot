import { previewKind } from "@/components/canvas/derive";
import type { FileEntry } from "./types";

/** Backend FileInfo ({path, name, size, mime, origin, modified_at}); older shapes carry mtime/kind. */
interface WireFile { path?: string; size?: number; mtime?: string; modified_at?: string; kind?: FileEntry["kind"] }

export const toFileEntries = (rows: WireFile[]): FileEntry[] =>
  rows.filter((r): r is WireFile & { path: string } => typeof r.path === "string").map((r) => ({
    path: r.path,
    size: typeof r.size === "number" ? r.size : 0,
    mtime: r.mtime ?? r.modified_at ?? "",
    kind: r.kind ?? previewKind(r.path),
  }));

const enc = encodeURIComponent;
/** Workspace file bytes (`render` serves html/svg as a sandboxed, script-enabled, network-less page). */
export const fileContentPath = (path: string, render = false): string => `/v1/files/content?path=${enc(path)}${render ? "&render=1" : ""}`;
