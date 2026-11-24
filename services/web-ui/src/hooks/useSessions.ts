"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type SessionInfo } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { chatStore } from "@/lib/store";
import type { PermissionMode } from "@/lib/stream/events";

export interface SessionsApi {
  sessions: SessionInfo[];
  loading: boolean;
  error: DotErrorInfo | null;
  activeId: string | null;
  active: SessionInfo | null;
  select: (id: string) => void;
  create: (mode?: PermissionMode) => Promise<void>;
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

  const reload = useCallback(async () => {
    try {
      const list = await api.sessions();
      setSessions(list);
      setError(null);
      if (first.current) {
        first.current = false;
        const want = readParam();
        const pick = list.find((s) => s.id === want) ?? list[0] ?? null;
        setActive(pick?.id ?? null);
        writeParam(pick?.id ?? null);
      }
    } catch (e) {
      setError(toErrorInfo(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    return chatStore.onTurnEnd(() => void reload());
  }, [reload]);

  const select = useCallback((id: string) => {
    setActive(id);
    writeParam(id);
  }, []);

  const create = useCallback(
    async (mode?: PermissionMode) => {
      const empty = sessions.find((s) => s.id === activeId);
      const cur = activeId ? chatStore.get(activeId) : null;
      if (!mode && empty && cur && cur.items.length === 0 && !cur.running && !empty.title) return;
      try {
        const s = await api.createSession(mode ?? sessions.find((x) => x.id === activeId)?.mode);
        setSessions((prev) => [s, ...prev.filter((x) => x.id !== s.id)]);
        select(s.id);
      } catch (e) {
        setError(toErrorInfo(e));
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

  const active = sessions.find((s) => s.id === activeId) ?? null;
  return { sessions, loading, error, activeId, active, select, create, setMode, reload };
}
