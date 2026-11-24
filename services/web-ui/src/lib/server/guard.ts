/** Request guards for the proxy: path allowlist, same-origin, loopback host. */

const PATH_OK = /^(v1(\/[A-Za-z0-9_.~-]+)+|ready|health)$/;

export function safeUpstreamPath(segments: string[]): string | null {
  if (segments.some((s) => s === "." || s === ".." || s === "" || /[/\\]/.test(s))) return null;
  const path = segments.join("/");
  return PATH_OK.test(path) ? path : null;
}

const LOOPBACK = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);

export function isLoopbackHost(hostname: string): boolean {
  return LOOPBACK.has(hostname.toLowerCase());
}

/** Resolve the backend base URL; non-loopback only when explicitly allowed. */
export function resolveBackend(raw: string | undefined, allowRemote: boolean): URL | null {
  let url: URL;
  try {
    url = new URL(raw?.trim() || "http://127.0.0.1:8000");
  } catch {
    return null;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  if (!allowRemote && !isLoopbackHost(url.hostname)) return null;
  return url;
}

function hostAllowed(host: string, extra: string[]): boolean {
  const name = host.replace(/:\d+$/, "");
  return isLoopbackHost(name) || extra.includes(host.toLowerCase());
}

export interface GuardInput {
  method: string;
  host: string | null;
  origin: string | null;
  fetchSite: string | null;
  extraHosts: string[];
}

/** Returns a rejection reason, or null when the request may proceed. */
export function checkRequest(i: GuardInput): string | null {
  if (!i.host || !hostAllowed(i.host, i.extraHosts)) return "host_not_allowed";
  const safe = i.method === "GET" || i.method === "HEAD";
  if (i.fetchSite && i.fetchSite !== "same-origin" && i.fetchSite !== "none") {
    if (!safe || i.fetchSite === "cross-site") return "cross_site";
  }
  if (!safe) {
    if (!i.origin) return "origin_required";
    let originHost: string;
    try {
      originHost = new URL(i.origin).host;
    } catch {
      return "bad_origin";
    }
    if (originHost.toLowerCase() !== i.host.toLowerCase()) return "cross_origin";
  }
  return null;
}
