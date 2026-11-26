"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BROWSER_BLOCKED, BROWSER_BUSY, BROWSER_DOWN, browserApi, fitViewport, type BrowserAction, type BrowserState } from "@/lib/api/browser";
import { feature, useCap } from "@/lib/api/caps";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { useApp } from "@/lib/state/app";

const POLL_MS = 1000;
/** While a page loads or an owner action is in flight: frames show the page as it paints. */
const FAST_MS = 250;
const DOWN_MS = 4000;
const FIT_MS = 200;
const FIT_RETRY_MS = 3000;
/** Owner actions that load a page: dim the old frame and show the loading line until they return. */
const LOADS = new Set<BrowserAction>(["navigate", "back", "forward", "reload", "tabs/new"]);

export interface BrowserNotice { kind: "blocked" | "busy" | "error"; text: string }
/** An owner action that loads a page, still waiting for the worker. */
export interface BrowserPending { action: BrowserAction; url?: string }
type Size = { width: number; height: number };

export function isBrowserTool(name: string): boolean {
  return name.startsWith("Browser");
}

/** Object URL of the latest frame; revoked on swap and dropped while inactive. */
function useFrameUrl(active: boolean): [string | null, (blob: Blob | null) => void] {
  const [frame, setFrame] = useState<string | null>(null);
  const swap = useCallback((blob: Blob | null) => {
    setFrame((old) => {
      if (old) URL.revokeObjectURL(old);
      return blob ? URL.createObjectURL(blob) : null;
    });
  }, []);
  useEffect(() => { if (!active) swap(null); }, [active, swap]);
  return [frame, swap];
}

/**
 * State + JPEG poll while `active` (tab visible, canvas open, document shown): about 1 fps when
 * idle, 4 fps while `fast` or the page is loading. `nonce` forces an immediate pull.
 */
function usePoll(active: boolean, nonce: number, fast: boolean) {
  const { id } = useApp();
  const available = useCap("browser");
  const [state, setState] = useState<BrowserState | null>(null);
  const [frame, swapFrame] = useFrameUrl(active);
  const [error, setError] = useState<DotErrorInfo | null>(null);
  const errorRef = useRef<DotErrorInfo | null>(null);
  const fastRef = useRef(fast);
  const loadingRef = useRef(false);
  const gen = useRef(0);
  useEffect(() => { errorRef.current = error; }, [error]);
  useEffect(() => { fastRef.current = fast; }, [fast]);
  useEffect(() => { loadingRef.current = !!state?.loading; }, [state?.loading]);

  useEffect(() => {
    if (!active || !id || !available) return;
    let stop = false;
    let timer = 0;
    const fresh = (g: number) => !stop && g === gen.current;
    const pull = async () => {
      const g = ++gen.current;
      try {
        const st = await feature("browser", () => browserApi.state(id));
        if (!fresh(g) || !st) return;
        setState(st);
        loadingRef.current = st.loading;
        setError(null);
        if (!st.open) {
          swapFrame(null);
          return;
        }
        // a frame can fail mid-navigation (document swap): keep the last one
        const got = await browserApi.frame(id, st.active).then((blob) => ({ blob }), () => null);
        if (fresh(g) && got) swapFrame(got.blob);
      } catch (e) {
        if (fresh(g)) setError(toErrorInfo(e));
      }
    };
    const delay = () => (errorRef.current?.code === BROWSER_DOWN ? DOWN_MS : fastRef.current || loadingRef.current ? FAST_MS : POLL_MS);
    const loop = async () => {
      if (document.visibilityState === "visible") await pull();
      if (!stop) timer = window.setTimeout(() => void loop(), delay());
    };
    const onVis = () => {
      if (document.visibilityState !== "visible") return;
      window.clearTimeout(timer);
      void loop();
    };
    document.addEventListener("visibilitychange", onVis);
    void loop();
    return () => {
      stop = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [active, id, available, nonce, swapFrame]);

  useEffect(() => { setState(null); setError(null); }, [id]);
  return { available, state, setState, frame, error, setError };
}

/**
 * Keeps the shared page the size of the panel (`size`, CSS px). Re-sent whenever the worker
 * reports another size (panel resized, new context, agent started the page). Runs even while
 * the agent acts: BrowserClick/BrowserType address elements by id, not pixel coordinates, so a
 * mid-run resize can't break the agent's own calls; a failed attempt for the same size waits
 * FIT_RETRY_MS.
 */
function useFit(active: boolean, size: Size | null, state: BrowserState | null, setState: (s: BrowserState) => void) {
  const { id } = useApp();
  const tried = useRef({ key: "", at: 0 });
  const want = size && size.width > 0 && size.height > 0 ? fitViewport(size.width, size.height) : null;
  const have = state?.viewport;
  const ok = !want || (have != null && have.width === want.width && have.height === want.height);
  useEffect(() => {
    if (!active || !id || !want || !state || ok) return;
    const key = `${id}:${want.width}x${want.height}`;
    const wait = tried.current.key === key ? Math.max(FIT_MS, tried.current.at + FIT_RETRY_MS - Date.now()) : FIT_MS;
    const t = window.setTimeout(() => {
      tried.current = { key, at: Date.now() };
      browserApi.act(id, "viewport", want).then(setState, () => undefined);
    }, wait);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed on the numbers, not object identity
  }, [active, id, want?.width, want?.height, !!state, acting, ok, setState]);
}

/**
 * Live view of the session's shared page, an immediate refresh after agent browser tool calls
 * and owner actions, and the page sized to the panel. Owner actions run one at a time, in order.
 */
export function useBrowser(active: boolean, size: Size | null = null) {
  const { id, chat } = useApp();
  const [nonce, setNonce] = useState(0);
  const [notice, setNotice] = useState<BrowserNotice | null>(null);
  const [inflight, setInflight] = useState(0);
  const [pending, setPending] = useState<BrowserPending | null>(null);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const kick = useCallback(() => setNonce((n) => n + 1), []);
  const poll = usePoll(active, nonce, inflight > 0);
  const { setState, setError } = poll;
  useEffect(() => { setNotice(null); setPending(null); }, [id]);

  // agent browser tool finished: refresh right away
  const finished = useMemo(() => chat.items.filter((i) => i.kind === "tool" && isBrowserTool(i.name) && i.status !== "running").length, [chat.items]);
  const running = useMemo(() => chat.items.some((i) => i.kind === "tool" && isBrowserTool(i.name) && i.status === "running"), [chat.items]);
  useEffect(() => { if (finished > 0) kick(); }, [finished, kick]);
  const acting = running || !!poll.state?.agent_acting;
  useFit(active, size, poll.state, setState);

  const act = useCallback((action: BrowserAction, body: object = {}): Promise<boolean> => {
    if (!id) return Promise.resolve(false);
    const loads = LOADS.has(action);
    setInflight((n) => n + 1);
    const run = async () => {
      setNotice(null);
      if (loads) {
        const url = (body as { url?: unknown }).url;
        setPending({ action, url: typeof url === "string" ? url : undefined });
        kick();
      }
      try {
        setState(await browserApi.act(id, action, body));
        setError(null);
        return true;
      } catch (e) {
        const info = toErrorInfo(e);
        if (info.code === BROWSER_DOWN) setError(info);
        else setNotice({ kind: info.code === BROWSER_BLOCKED ? "blocked" : info.code === BROWSER_BUSY ? "busy" : "error", text: info.title });
        return false;
      } finally {
        if (loads) setPending(null);
        setInflight((n) => n - 1);
        kick();
        window.setTimeout(kick, 400); // pages often react a beat after input
      }
    };
    const p = queue.current.then(run, run);
    queue.current = p;
    return p;
  }, [id, kick, setState, setError]);

  return { available: poll.available, state: poll.state, frame: poll.frame, error: poll.error, notice, pending, acting, act, retry: kick, dismiss: () => setNotice(null) };
}
