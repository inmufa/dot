# Dot web cockpit

Browser UI for the local Dot agent: sessions, streaming chat, tool calls, approvals with diffs, permission modes, rewind, skills, audit log, questions, subagents, plans, context and compaction, tasks, memory, tools, MCP servers and schedules. Next.js 15 (App Router), React 19, TypeScript.

The browser never sees the API token. Every call goes to `/api/dot/*`, a server-side proxy that adds `Authorization: Bearer <DOT_API_TOKEN>` and streams the backend's SSE through untouched.

## Run

Needs Node 22+ and a running Dot backend.

```bash
cd services/web-ui
cp .env.example .env.local     # set DOT_API_TOKEN
npm install
npm run dev                    # http://127.0.0.1:3000
```

Production: `npm run build && npm start` (binds to 127.0.0.1 only). Docker: `docker build -f deploy/docker/web/Dockerfile services/web-ui`.

## Environment (server side only)

| Variable | Default | Meaning |
|---|---|---|
| `DOT_URL` | `http://127.0.0.1:8000` | Backend base URL. Must be loopback unless `DOT_ALLOW_NON_LOOPBACK=1`. |
| `DOT_API_TOKEN` | none | Backend bearer token. Required. |
| `DOT_ALLOW_NON_LOOPBACK` | empty | Set to `1` when the backend is a compose service name. |
| `DOT_WEB_ALLOWED_HOSTS` | empty | Extra `Host` values accepted by the proxy, comma list. |

The proxy only forwards `v1/*`, `ready` and `health`, rejects cross-origin writes and unknown `Host` headers, and aborts the upstream request when the browser disconnects.

## Using it

- `Enter` sends, `Shift+Enter` adds a line, `/` opens commands (`/mode`, `/stop`, `/rewind`, `/new` and every skill), `Esc` stops a running turn.
- Approvals: `a` allow once, `s` allow for the session, `r` reject. Keys arm after a short delay so a stray keypress cannot approve.
- The dot shows state everywhere, including the tab icon: grey idle, amber thinking, blue needs approval.
- Bypass mode asks for confirmation. Theme and the message language for backend errors live in Settings.
- Questions: Dot's `AskUserQuestion` shows a card above the composer: `1`-`4` pick, `Enter` sends, "Other" takes free text, a countdown shows the 5 minute timeout.
- Subagents show as a collapsible line under the `Agent` call; their approvals carry a "from <label>" badge. `ExitPlanMode` approvals show the plan as rendered markdown ("Approve plan" / "Keep planning"); approved plans stay in the transcript.
- Reject is always instant; the allow buttons fill for 0.7 s, then switch to their real style.
- The context meter opens a popover (prompt layers, messages, compactions) with a Compact button. Compactions appear as a quiet divider.
- Tool results marked untrusted carry a shield icon.
- Side panels (rail): Tasks (per session), Memory (search, add, edit, delete), Skills, Tools (core vs deferred), MCP (status, reconnect, trust for project servers), Schedules (cron preview in this browser's time zone, create, delete), Audit log.
- Per-session running/waiting state in the rail is tracked in this browser only: the backend's session list does not expose it, so a turn started elsewhere shows as idle.
- Not wired (no backend endpoint): GPU/VRAM telemetry.

## Develop

```bash
npm run typecheck && npm run lint && npm test
npm run build && npm run e2e         # Playwright against scripts/mock-backend.mjs; also runs axe-core (serious/critical fail); screenshots in shots/
npm run e2e -- --worst               # adds long strings, huge output, 500 sessions, RTL text and worst-case data for every panel (100 tasks, 200 facts, 50 MCP tools)
```

`npm run mock` starts the mock backend alone (port 8765, token `mock-token`): prompts containing `edit` or `bash` trigger an approval, `ask` (add `multi`) a question, `agent` subagents plus a tainted result, `plan` a plan approval, `compact` a compaction, `web` a tainted fetch, `code` returns markdown, `long` returns worst-case output.
Playwright uses the Chromium cached in `~/.cache/ms-playwright`.
