import type { ErrorKind } from "./errors";

/** What to do next, per backend code range. Codes: core 1000s, session 2000s, governance 3000s, tools 4000s. */
const BY_CODE: Record<number, string> = {
  1000: "Check the backend log for the cause.",
  1002: "That item no longer exists. Refresh the list.",
  1008: "A dependency is down: the database, the sandbox or the model server. Check /ready on the backend.",
  2000: "The session was not found. Start a new one.",
  2001: "Wait for the running turn to finish, or press Stop.",
  2002: "That point in history is no longer valid. Reload the session.",
  3000: "A permission rule or the current mode refused this call.",
  3001: "Nobody answered in time. Send the message again to retry.",
  3003: "That approval was already resolved or expired.",
  3004: "Restoring files failed. Retrying resumes where it stopped.",
  3005: "A settings.json file is invalid. Fix it, the backend fails closed.",
  3006: "A UserPromptSubmit hook blocked this message.",
  3007: "A checkpoint could not be taken, so the edit was not run.",
  4000: "The model server is down. Start llama.cpp and retry.",
  4001: "The sandbox runner is down. Start it and retry.",
  4003: "The model produced malformed tool calls twice. Rephrase and retry.",
};

const BY_KIND: Record<ErrorKind, string | null> = {
  offline: "Check that the backend is running and DOT_URL points at it.",
  unauthorized: "Set DOT_API_TOKEN on the web UI server to the backend token.",
  busy: "Wait for the running turn to finish, or press Stop.",
  notfound: null,
  server: null,
};

export function hintFor(code: number | null, kind: ErrorKind): string | null {
  return (code !== null ? BY_CODE[code] : undefined) ?? BY_KIND[kind];
}
