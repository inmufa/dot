import { resolveBackend } from "./guard";

export function serverEnv() {
  return {
    backend: resolveBackend(process.env.DOT_URL, process.env.DOT_ALLOW_NON_LOOPBACK === "1"),
    token: process.env.DOT_API_TOKEN ?? "",
    extraHosts: (process.env.DOT_WEB_ALLOWED_HOSTS ?? "")
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean),
  };
}

export function proxyError(status: number, key: string, code: number, text: string): Response {
  const body = [{ key, code, show: true, icon_type: "error", type: "proxy_error", messages: [text] }];
  return Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
}
