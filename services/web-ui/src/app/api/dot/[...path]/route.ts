import { serverEnv, proxyError } from "@/lib/server/env";
import { checkRequest, safeUpstreamPath } from "@/lib/server/guard";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const FORWARD_REQ = ["content-type", "accept", "accept-language", "range", "if-none-match", "if-modified-since"];
const FORWARD_RES = ["content-type", "content-language", "content-security-policy", "x-sample-rate",
  "etag", "last-modified", "accept-ranges", "content-range", "content-length", "content-disposition", "x-content-type-options"];

async function handle(req: Request, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const env = serverEnv();
  const bad = checkRequest({
    method: req.method,
    host: req.headers.get("host"),
    origin: req.headers.get("origin"),
    fetchSite: req.headers.get("sec-fetch-site"),
    extraHosts: env.extraHosts,
  });
  if (bad) return proxyError(403, bad, 1000, "Request refused by the web UI proxy.");

  const path = safeUpstreamPath((await ctx.params).path);
  if (!path) return proxyError(404, "path_not_allowed", 1002, "Unknown path.");
  if (!env.backend) return proxyError(500, "bad_dot_url", 1000, "DOT_URL is invalid or not loopback.");
  if (!env.token) return proxyError(500, "no_token", 1000, "DOT_API_TOKEN is not set on the web UI server.");

  const url = new URL(`/${path}${new URL(req.url).search}`, env.backend);
  const headers = new Headers({ Authorization: `Bearer ${env.token}` });
  for (const h of FORWARD_REQ) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      signal: req.signal, // client disconnect aborts the upstream stream
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return proxyError(502, "backend_unreachable", 1008, "Dot backend is unreachable.");
  }

  // Media bytes may be cached privately; everything else stays uncached.
  const media = path === "v1/media" && upstream.ok;
  const out = new Headers({ "Cache-Control": media ? "private, max-age=3600" : "no-cache, no-transform", "X-Accel-Buffering": "no" });
  for (const h of FORWARD_RES) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { handle as GET, handle as POST, handle as DELETE, handle as PUT, handle as PATCH };
