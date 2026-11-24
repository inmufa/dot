"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";

export type Link = "checking" | "online" | "degraded" | "offline";

export function useConnection(): { link: Link; error: DotErrorInfo | null; recheck: () => void } {
  const [link, setLink] = useState<Link>("checking");
  const [error, setError] = useState<DotErrorInfo | null>(null);

  const check = useCallback(async () => {
    try {
      await api.ready();
      setLink("online");
      setError(null);
    } catch (e) {
      const info = toErrorInfo(e);
      setError(info);
      // 503 from /ready means the backend is up but a dependency is down.
      setLink(info.status === 503 && info.code !== null ? "degraded" : info.kind === "unauthorized" ? "online" : "offline");
    }
  }, []);

  useEffect(() => {
    void check();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void check();
    }, 15_000);
    const onVis = () => {
      if (document.visibilityState === "visible") void check();
    };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("online", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("online", onVis);
    };
  }, [check]);

  return { link, error, recheck: () => void check() };
}
