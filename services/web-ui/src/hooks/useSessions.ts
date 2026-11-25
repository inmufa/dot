"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type SessionInfo } from "@/lib/api/client";
import { feature } from "@/lib/api/caps";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { chatStore } from "@/lib/state/store";
import type { PermissionMode } from "@/lib/stream/events";

export interface SessionsApi {
  sessions: SessionInfo[];
  loading: boolean;
  error: DotErrorInfo | null;
  activeId: string | null;
  active: SessionInfo | null;
  select: (id: string) => void;
  /** Returns the new (or reused empty) session id, null on failure. */
  create: (mode?: PermissionMode, project?: string | null) => Promise<string | null>;
  patch: (id: string, p: { title?: string; pinned?: boolean; archived?: boolean }) => Promise<DotErrorInfo | null>;
  remove: (id: string) => Promise<DotErrorInfo | null>;
  setMode: (mode: PermissionMode) => Promise<DotErrorInfo | null>;
  reload: () => Promise<void>;
}

const readParam = (): string | null => new URLSearchParams(window.location.search).get("s");
function writeParam(id: string | null): void {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("s", id);
  else url.searchParams.delete("s");
  window.history.replaceState(null, "", url);
}

export function useSessions(): SessionsApi {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DotErrorInfo | null>(null);
  const [activeId, setActive] = useState<string | null>(null);
  const first = useRef(true);
  const activeRef = useRef<string | null>(null);
  useEffect(() => { activeRef.current = activeId; }, [activeId]);

  // An empty chat stays out of the sidebar until its first message
  const fresh = useCallback(async (list: SessionInfo[]) => {
    const empty = list.find((x) => !x.title && !x.message_count && (x.state ?? "idle") === "idle");
    if (empty) {
      setActive(empty.id);
      writeParam(empty.id);
      return;
    }
    const s = await api.createSession();
    setSessions([s, ...list]);
    setActive(s.id);
    writeParam(s.id);
  }, []);

  const reload = useCallback(async () => {
    try {
      const list = await api.sessions();
      setSessions(list);
      setError(null);
      if (first.current) {
        first.current = false;
        const want = readParam();
        const pick = list.find((s) => s.id === want) ?? list[0] ?? null;
        if (pick) {
          setActive(pick.id);
          writeParam(pick.id);
        } else {
          await fresh(list); // nothing to open: start an empty chat so the composer is live
        }
      } else if (activeRef.current && !list.some((s) => s.id === activeRef.current)) {
        // Deleted elsewhere? Recheck once, so a chat created a moment ago is not dropped
        const gone = activeRef.current;
        await new Promise((r) => setTimeout(r, 1500));
        const again = await api.sessions();
        if (activeRef.current === gone && !again.some((s) => s.id === gone)) {
          await fresh(again);
        }
      }
    } catch (e) {
      setError(toErrorInfo(e));
    } finally {
      setLoading(false);
    }
  }, [fresh]);

  useEffect(() => {
    void reload();
    const onVisible = () => { if (document.visibilityState === "visible") void reload(); };
    document.addEventListener("visibilitychange", onVisible);
    // The AI title lands a moment after the turn ends: refresh again shortly after
    const timers = new Set<number>();
    const off = chatStore.onTurnEnd(() => {
      void reload();
      const t = window.setTimeout(() => { timers.delete(t); void reload(); }, 3500);
      timers.add(t);
    });
    return () => { off(); document.removeEventListener("visibilitychange", onVisible); timers.forEach((t) => window.clearTimeout(t)); };
  }, [reload]);

  // Always keep one chat open (e.g. after deleting the last one) so the composer never sits disabled
  useEffect(() => {
    if (loading || error || activeId) return;
    void fresh(sessions).catch((e: unknown) => setError(toErrorInfo(e)));
  }, [loading, error, activeId, sessions, fresh]);

  const select = useCallback((id: string) => {
    setActive(id);
    writeParam(id);
  }, []);

  const create = useCallback(
    async (mode?: PermissionMode, project?: string | null) => {
      const empty = sessions.find((s) => s.id === activeId);
      const cur = activeId ? chatStore.get(activeId) : null;
      if (!mode && !project && empty && cur && cur.items.length === 0 && !cur.running && !empty.title) return empty.id;
      try {
        const s = await api.createSession(mode ?? sessions.find((x) => x.id === activeId)?.mode, project);
        setSessions((prev) => [s, ...prev.filter((x) => x.id !== s.id)]);
        select(s.id);
        return s.id;
      } catch (e) {
        setError(toErrorInfo(e));
        return null;
      }
    },
    [sessions, activeId, select],
  );

  const setMode = useCallback(
    async (mode: PermissionMode) => {
      if (!activeId) return null;
      try {
        const s = await api.setMode(activeId, mode);
        setSessions((prev) => prev.map((x) => (x.id === s.id ? { ...x, mode: s.mode } : x)));
        return null;
      } catch (e) {
        return toErrorInfo(e);
      }
    },
    [activeId],
  );

  const patch = useCallback(async (id: string, p: { title?: string; pinned?: boolean; archived?: boolean }) => {
    const before = sessions;
    setSessions((prev) => prev.map((x) => (x.id === id ? { ...x, ...p } : x)));
    try {
      const r = await feature("pin", () => api.patchSession(id, p));
      if (r === null) setSessions(before);
      else setSessions((prev) => prev.map((x) => (x.id === id ? { ...x, ...r } : x)));
      return r === null ? { kind: "notfound", status: 404, code: null, title: "Not available yet.", hint: null, retryable: false } satisfies DotErrorInfo : null;
    } catch (e) {
      setSessions(before);
      return toErrorInfo(e);
    }
  }, [sessions]);

  const remove = useCallback(async (id: string) => {
    try {
      await feature("pin", () => api.deleteSession(id));
      chatStore.reset(id);
      setSessions((prev) => {
        const left = prev.filter((x) => x.id !== id);
        if (id === activeId) {
          const nxt = left.find((x) => !x.archived)?.id ?? null;
          setActive(nxt);
          writeParam(nxt);
        }
        return left;
      });
      return null;
    } catch (e) {
      return toErrorInfo(e);
    }
  }, [activeId]);

  const active = sessions.find((s) => s.id === activeId) ?? null;
  return { sessions, loading, error, activeId, active, select, create, patch, remove, setMode, reload };
}
