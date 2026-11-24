"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";

export interface Resource<T> {
  data: T | null;
  error: DotErrorInfo | null;
  loading: boolean;
  reload: () => void;
  set: (v: T | null) => void;
}

/** Load once when `enabled` flips on (a panel opens); `every` re-polls while enabled. Stale responses are dropped. */
export function useResource<T>(load: () => Promise<T>, enabled: boolean, every = 0, key = ""): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<DotErrorInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const fn = useRef(load);
  const gen = useRef(0);
  useEffect(() => {
    fn.current = load;
  });

  const run = useCallback((quiet: boolean) => {
    const g = ++gen.current;
    if (!quiet) setLoading(true);
    fn.current().then(
      (d) => {
        if (g !== gen.current) return;
        setData(d);
        setError(null);
        setLoading(false);
      },
      (e: unknown) => {
        if (g !== gen.current) return;
        setError(toErrorInfo(e));
        setLoading(false);
      },
    );
  }, []);

  useEffect(() => {
    if (!enabled) return;
    run(false);
    if (!every) return;
    const t = window.setInterval(() => run(true), every);
    return () => window.clearInterval(t);
  }, [enabled, every, key, run]);

  const reload = useCallback(() => run(false), [run]);
  const set = useCallback((v: T | null) => setData(v), []);
  return { data, error, loading, reload, set };
}
