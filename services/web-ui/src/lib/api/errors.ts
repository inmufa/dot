import { hintFor } from "./error-text";

export interface EnvelopeEntry {
  key: string | null;
  code: number;
  show: boolean;
  type: string;
  messages: string[];
}

export type ErrorKind = "offline" | "unauthorized" | "busy" | "notfound" | "server";

export interface DotErrorInfo {
  kind: ErrorKind;
  status: number;
  code: number | null;
  title: string;
  hint: string | null;
  retryable: boolean;
}

/** Normalise the backend error envelope list; anything else yields []. */
export function parseEnvelope(body: unknown): EnvelopeEntry[] {
  if (!Array.isArray(body)) return [];
  const out: EnvelopeEntry[] = [];
  for (const raw of body) {
    if (typeof raw !== "object" || raw === null) continue;
    const r = raw as Record<string, unknown>;
    if (typeof r.code !== "number") continue;
    out.push({
      key: typeof r.key === "string" ? r.key : null,
      code: r.code,
      show: r.show !== false,
      type: typeof r.type === "string" ? r.type : "domain_error",
      messages: Array.isArray(r.messages) ? r.messages.filter((m): m is string => typeof m === "string") : [],
    });
  }
  return out;
}

function kindFor(status: number, code: number | null): ErrorKind {
  if (status === 0 || status === 502 || status === 503 || status === 504) return "offline";
  if (status === 401 || status === 403) return "unauthorized";
  if (code === 2001 || status === 409) return "busy";
  if (status === 404) return "notfound";
  return "server";
}

/** Map an HTTP status + envelope to a message. Server text (already localised via Accept-Language) wins when `show`. */
export function describeError(status: number, body: unknown): DotErrorInfo {
  const entries = parseEnvelope(body);
  const first = entries[0];
  const code = first?.code ?? null;
  const kind = kindFor(status, code);
  const serverText = first?.show ? first.messages.join(" ") : "";
  const hint = hintFor(code, kind);
  const fallback: Record<ErrorKind, string> = {
    offline: "Dot backend is unreachable.",
    unauthorized: "The backend rejected the web UI token.",
    busy: "This session is busy with another turn.",
    notfound: "Not found.",
    server: "Something went wrong on the backend.",
  };
  return {
    kind,
    status,
    code,
    title: serverText || fallback[kind],
    hint,
    retryable: kind === "offline" || kind === "busy" || status >= 500,
  };
}

export class DotApiError extends Error {
  constructor(public info: DotErrorInfo) {
    super(info.title);
    this.name = "DotApiError";
  }
}

export function toErrorInfo(e: unknown): DotErrorInfo {
  if (e instanceof DotApiError) return e.info;
  return describeError(0, null);
}
