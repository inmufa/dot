"use client";
import { FileText, ImageIcon, RotateCw, TriangleAlert, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Lightbox } from "@/components/chat/Lightbox";
import { api } from "@/lib/api/client";
import { feature } from "@/lib/api/caps";
import { toErrorInfo } from "@/lib/api/errors";
import type { ToastInput } from "@/components/ui";

export const MAX_FILES = 5;
export const MAX_BYTES = 20 * 1024 * 1024;

export interface Att {
  key: string;
  name: string;
  size: number;
  kind: "image" | "doc" | "text";
  status: "uploading" | "done" | "error";
  id?: string;
  error?: string;
  preview?: string;
}

const kindOf = (f: File): Att["kind"] => (f.type.startsWith("image/") ? "image" : f.type.startsWith("text/") ? "text" : "doc");
export const sizeText = (n: number): string => (n < 1024 ? `${n} B` : n < 1048576 ? `${Math.round(n / 1024)} kB` : `${(n / 1048576).toFixed(1)} MB`);

/** Upload state for the composer: validate, upload in parallel, keep the ids to send. */
export function useAttachments(sessionId: string | null, notify: (t: ToastInput) => void) {
  const [items, setItems] = useState<Att[]>([]);
  const live = useRef(items);
  useEffect(() => {
    live.current = items;
  }, [items]);
  useEffect(() => {
    setItems([]);
  }, [sessionId]);
  useEffect(() => () => live.current.forEach((a) => a.preview && URL.revokeObjectURL(a.preview)), []);

  const patch = useCallback((key: string, p: Partial<Att>) => setItems((l) => l.map((a) => (a.key === key ? { ...a, ...p } : a))), []);

  const files_ = useRef(new Map<string, File>());
  const failed = useRef<string[]>([]);
  const flush = useRef<number>(0);
  const upload = useCallback((key: string, f: File) => {
    if (!sessionId) return;
    feature("attachments", () => api.upload(sessionId, f)).then(
      (r) => {
        if (r) patch(key, { status: "done", id: r.id });
        else { patch(key, { status: "error", error: "Not available yet" }); notify({ title: "Attachments are not available yet", tone: "warn" }); }
      },
      (e: unknown) => {
        const why = toErrorInfo(e).title;
        patch(key, { status: "error", error: why });
        failed.current.push(f.name);
        window.clearTimeout(flush.current);
        flush.current = window.setTimeout(() => {
          const n = failed.current.splice(0);
          notify({ title: n.length === 1 ? `Could not upload ${n[0]}` : `Could not upload ${n.length} files`, description: why, tone: "bad" });
        }, 250);
      },
    );
  }, [sessionId, notify, patch]);

  const add = useCallback((files: File[]) => {
    if (!sessionId || !files.length) return;
    const room = MAX_FILES - live.current.length;
    if (room <= 0) {
      notify({ title: `At most ${MAX_FILES} attachments per message`, tone: "warn" });
      return;
    }
    if (files.length > room) notify({ title: `Only ${MAX_FILES} attachments fit`, description: "Extra files were skipped.", tone: "warn" });
    for (const f of files.slice(0, room)) {
      const key = `${f.name}-${f.size}-${Math.random().toString(36).slice(2, 7)}`;
      const base: Att = { key, name: f.name, size: f.size, kind: kindOf(f), status: "uploading" };
      if (f.size > MAX_BYTES) {
        setItems((l) => [...l, { ...base, status: "error", error: "Over 20 MB" }]);
        notify({ title: `${f.name} is over 20 MB`, tone: "bad" });
        continue;
      }
      setItems((l) => [...l, { ...base, ...(base.kind === "image" ? { preview: URL.createObjectURL(f) } : {}) }]);
      files_.current.set(key, f);
      upload(key, f);
    }
  }, [sessionId, notify, upload]);

  const retry = useCallback((key: string) => {
    const f = files_.current.get(key);
    if (!f) return;
    patch(key, { status: "uploading", error: undefined });
    upload(key, f);
  }, [upload, patch]);

  const remove = useCallback((key: string) => {
    setItems((l) => {
      const p = l.find((a) => a.key === key)?.preview;
      if (p) URL.revokeObjectURL(p);
      return l.filter((a) => a.key !== key);
    });
  }, []);
  const clear = useCallback(() => setItems([]), []);
  return { items, add, remove, retry, clear, busy: items.some((a) => a.status === "uploading"), ids: items.flatMap((a) => (a.status === "done" && a.id ? [a.id] : [])) };
}

/** Image attachments are square thumbnails (no name); other files are a tile with the extension. x on hover; errors say why and can retry. */
export function AttachChips({ items, onRemove, onRetry, vision }: { items: Att[]; onRemove: (k: string) => void; onRetry: (k: string) => void; vision: boolean }) {
  const [view, setView] = useState<number | null>(null);
  if (!items.length) return null;
  const imgs = items.filter((a) => a.preview);
  return (
    <>
    <ul className="atts" aria-label="Attachments">
      {items.map((a) => {
        const ext = a.name.includes(".") ? a.name.split(".").pop()?.slice(0, 4).toUpperCase() : "FILE";
        const note = a.error ?? (a.kind === "image" && !vision ? "The model cannot see images yet. The file is still stored." : a.name);
        return (
          <li key={a.key} className="att" data-status={a.status} data-kind={a.kind} title={note}>
            <span className="att-tile">
              {a.preview ? (
                <button type="button" className="att-open" onClick={() => setView(imgs.indexOf(a))} aria-label={`Open ${a.name}`}><img src={a.preview} alt="" /></button>
              ) : a.status === "error" ? (
                <TriangleAlert size={20} aria-hidden />
              ) : a.kind === "image" ? (
                <ImageIcon size={20} aria-hidden />
              ) : (
                <span className="att-file"><FileText size={18} aria-hidden /><span className="att-ext">{ext}</span></span>
              )}
              {a.status === "uploading" && <span className="att-bar" aria-hidden />}
              {a.status === "error" && a.preview && <span className="att-err" aria-hidden><TriangleAlert size={16} /></span>}
              {a.status === "error" && a.error !== "Over 20 MB" && (
                <button type="button" className="att-retry" onClick={() => onRetry(a.key)} aria-label={`Retry ${a.name}: ${a.error ?? "failed"}`}>
                  <RotateCw size={14} aria-hidden />
                </button>
              )}
            </span>
            <button type="button" className="att-x" onClick={() => onRemove(a.key)} aria-label={`Remove ${a.name}`}>
              <X size={12} aria-hidden />
            </button>
            {a.status === "error" && (
              <>
                <span className="att-cap rec" role="alert">{a.error === "Over 20 MB" ? "over 20 MB" : "failed"}</span>
                <span className="sr-only">{a.error}</span>
              </>
            )}
          </li>
        );
      })}
    </ul>
    <Lightbox items={imgs.map((a) => ({ src: a.preview ?? "", name: a.name }))} index={view} onIndex={setView} onClose={() => setView(null)} />
    </>
  );
}
