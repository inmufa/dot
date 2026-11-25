import { apiHeaders, BASE, request } from "./client";
import { DotApiError, describeError } from "./errors";

export interface BrowserTabInfo { tab: string; url: string; title: string }
/** Page URLs, titles and the block reason come from the page or guard: untrusted text, render as text only. */
export interface BrowserState {
  open: boolean;
  tabs: BrowserTabInfo[];
  active: string | null;
  url: string;
  title: string;
  loading: boolean;
  /** Absent on older backends: treat as true. */
  can_back?: boolean;
  can_forward?: boolean;
  viewport: { width: number; height: number } | null;
  blocked: string | null;
  agent_acting: boolean;
  agent_seq: number;
  status?: number | null;
}

export type BrowserAction =
  | "navigate" | "back" | "forward" | "reload" | "click" | "type" | "press" | "scroll"
  | "tabs/new" | "tabs/switch" | "tabs/close" | "viewport";

/** Worker not reachable (compose profile `browser` is not up). */
export const BROWSER_DOWN = 4015;
export const BROWSER_BUSY = 4017;
export const BROWSER_BLOCKED = 4018;
export const PAGE_FAILED = 4019;

/** Worker bounds for the page size (POST /viewport); the panel is clamped into them. */
export const VIEWPORT = { minW: 320, maxW: 1920, minH: 320, maxH: 1600 } as const;
export function fitViewport(w: number, h: number): { width: number; height: number } {
  const c = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, Math.floor(v)));
  return { width: c(w, VIEWPORT.minW, VIEWPORT.maxW), height: c(h, VIEWPORT.minH, VIEWPORT.maxH) };
}

const base = (id: string) => `/v1/sessions/${encodeURIComponent(id)}/browser`;

export const browserApi = {
  state: (id: string) => request<BrowserState>(`${base(id)}/state`),
  act: (id: string, action: BrowserAction, body: object = {}) =>
    request<BrowserState>(`${base(id)}/${action}`, { method: "POST", body: JSON.stringify(body) }),
  /** Latest frame as an image blob; null when no page is open (204). */
  async frame(id: string, tab?: string | null): Promise<Blob | null> {
    let res: Response;
    try {
      res = await fetch(`${BASE}${base(id)}/frame`, {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(tab ? { tab } : {}),
        cache: "no-store",
      });
    } catch {
      throw new DotApiError(describeError(0, null));
    }
    if (res.status === 204) return null;
    if (!res.ok) throw new DotApiError(describeError(res.status, await res.json().catch(() => null)));
    return res.blob();
  },
};

const SCHEME = /^[a-z][a-z0-9+.-]*:\/\//i;
/** Address-bar input to a URL: bare hosts get https. */
export const normalizeUrl = (v: string): string => (SCHEME.test(v.trim()) ? v.trim() : `https://${v.trim()}`);
