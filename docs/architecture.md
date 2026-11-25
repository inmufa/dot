# Architecture

Dot is a self-hosted coding and research agent for one person on one workstation. A local model runs in llama.cpp, and a deterministic harness (the backend) turns its output into tool calls that are checked, approved and executed in a sandbox.

## Services and data flow

```
 host (127.0.0.1 only)
 +-------------------+      +-------------------+
 | browser (web UI)  |      | `dot` TUI (host)  |
 +---------+---------+      +---------+---------+
           | http :3000               | http :8000 (bearer token)
 +---------v---------+                |
 |      dot-web      |  server-side   |
 | (Next.js, holds   +----------------+
 |  the API token)   |
 +---------+---------+
           | DOT_URL, bearer token
 +---------v----------------------------------------------+
 |                      dot-backend                       |
 | agent loop, permissions, hooks, compaction, skills,    |
 | memory, MCP client, scheduler, SQLite (WAL, FTS5)      |
 +---+----------+-----------+-------------+------------+--+
     |          |           |             |            |
     | OpenAI   | HTTP +    | HTTP        | HTTP +     | HTTPS via
     | chat API | token     |             | token      | SSRF guard
 +---v----+ +---v------+ +--v-------+ +---v--------+ +-v-----------+
 |dot-llm | |dot-      | |dot-      | |dot-browser | | public web  |
 |llama.  | |sandbox   | |searxng   | |(profile    | | (WebFetch)  |
 |cpp     | |(only     | |(search)  | | "browser") | +-------------+
 |Vulkan  | | writer of| +----------+ +-----+------+
 +--------+ |/workspace|                    | egress network
            | + stdio  |                    v  (firewall script blocks LAN)
            |MCP procs |                  internet
            +----------+
```

- `dot-llm` serves the model (`--parallel 2`, 32k tokens per slot). Only the backend talks to it.
- `dot-sandbox` is the only component that writes to the workspace. It runs shell commands, file operations, linters and stdio MCP servers. The backend mounts the workspace read-only.
- `dot-searxng` answers `WebSearch`. It is internal and not published.
- `dot-browser` is optional (`make up-browser`). The backend reaches it over `dot-browser-link`, an internal network with no egress. Its own network `dot-browsing` has egress, which you can restrict with `deploy/scripts/firewall_dot.sh`.
- The web UI "Browser" canvas tab shows the same page live: it polls JPEG frames from `/v1/sessions/{id}/browser/frame` and can click, type and scroll. Owner input is refused while the agent acts.
- State: SQLite in the `dot-data` volume (sessions, messages, audit, schedules, MCP trust), long-term memory files in the `dot-memory` volume (backend only), your project files in the host workspace folder.

Only 127.0.0.1 ports are published: llm 8080, backend 8000, browser 8091, web 3000. The sandbox has no published port. Networks, what may reach the internet and why: `docs/privacy.md`.

## One turn

1. The client sends `POST /v1/sessions/{id}/chat`. The backend checks the token, the size limits and the rate limit.
2. The engine builds the prompt: a byte-stable prefix (system prompt, core tool schemas), then the per-session suffix (rules, memory index), then the append-only transcript. Only compaction rewrites history.
3. The backend streams the request to llama-server and forwards tokens (thinking and answer) as SSE events.
4. For each tool call the governance pipeline runs: settings rules, PreToolUse hooks, mode, classifier (auto mode only), then the user if needed. Every decision is written to the audit table.
5. Allowed calls run: file and shell tools in the sandbox, web tools in the backend or browser worker, memory and tasks in the backend.
6. The result goes back to the model as a tool message. The loop repeats until the model answers, the iteration cap is hit, or the turn is stopped.

## Trust boundaries

| Zone | Trust | Why |
|---|---|---|
| You, the API token holder | Trusted | The single user. The token in `.env` is the only credential for the API. |
| Backend code and its settings | Trusted | Enforces the rules. Never executes model output directly. |
| Baseline rules and files mounted read-only (`.dot/settings.json`, `.dot/hooks`) | Trusted, protected | A shell command in the sandbox cannot change them. |
| The model's output | Untrusted | It proposes calls; the pipeline decides. Tool arguments are validated and malformed calls are rejected. |
| Sandbox container | Contained | Runs model-chosen commands as uid 1000, no capabilities, no host mounts except the workspace. It is the real boundary, not the lexical rules. |
| Workspace content (files, `DOT.md`, workspace skills, project MCP config) | Untrusted | Anyone who can put a file in a repo can influence the agent. Workspace skills are tainted; project MCP servers need your approval. |
| Web pages, search results, browser content, MCP tool results, memory recall | Untrusted and tainted | The text may contain prompt injection. |

**Tainted** is a flag on tool results that carry untrusted text. In auto mode, a mutating call that follows tainted input with no user message in between is escalated to an approval, and so is any call whose arguments share a long substring with tainted text. A subagent that read web content reports itself as tainted to its parent.

See `docs/security.md` for the threats each layer covers and `docs/api-contract.md` for the wire details.
