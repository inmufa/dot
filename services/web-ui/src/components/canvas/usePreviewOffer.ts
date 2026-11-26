"use client";
import { useMemo, useState } from "react";
import { useApp } from "@/lib/state/app";
import { writtenFiles, type FileKind } from "./derive";

export interface PreviewOffer {
  path: string;
  kind: FileKind;
  open: () => void;
  dismiss: () => void;
}

/** Latest previewable file the agent wrote; null when none, dismissed or open. */
export function usePreviewOffer(): PreviewOffer | null {
  const { chat, ui } = useApp();
  const [gone, setGone] = useState<Set<string>>(new Set());
  const last = useMemo(() => writtenFiles(chat.items).filter((f) => f.kind !== "code" && f.kind !== "other").at(-1) ?? null, [chat.items]);
  if (!last || gone.has(last.path) || (ui.canvas.open && ui.canvas.tab === "preview" && ui.canvas.path === last.path)) return null;
  return {
    ...last,
    open: () => ui.openCanvas("preview", last.path),
    dismiss: () => setGone((g) => new Set(g).add(last.path)),
  };
}
