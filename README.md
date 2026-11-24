# Dot

Dot is a self-hosted coding and research agent that runs entirely on your own machine. A local GGUF model served by llama.cpp (Vulkan, built for an AMD RX 580 class GPU) is wrapped in a harness modelled on Claude Code: file and shell tools, permission modes, hooks, skills, subagents, MCP servers, memory, compaction and file checkpoints you can rewind. It is built for one person on one workstation and listens on 127.0.0.1 only.

## Requirements

- Linux with Docker Engine and the compose plugin (`deploy/scripts/install_docker.sh` installs them on Ubuntu).
- A GPU with Vulkan support and about 8 GB of VRAM (developed on an RX 580), plus about 6 GB of free RAM.
- [uv](https://docs.astral.sh/uv/) and Python 3.12 for the `dot` terminal client and for development.
- A GGUF model file. Dot does not ship one.

## Quick start

```
cp .env.example .env     # set DOT_API_TOKEN, DOT_SANDBOX_TOKEN, SEARXNG_SECRET (openssl rand -hex 32)
mkdir -p workspace models
make init                # prepares workspace/.dot
make models              # downloads the model named in .env, see "Models"
make up
```

Open http://127.0.0.1:3000 for the web cockpit. The backend API is on http://127.0.0.1:8000.

### Configuration

Everything is configured in `.env` (copy of `.env.example`, git-ignored). The important keys:

| Key | Meaning |
|---|---|
| `DOT_API_TOKEN` | Bearer token for the API and the web UI server. Required, at least 16 characters. |
| `DOT_SANDBOX_TOKEN`, `SEARXNG_SECRET` | Secrets between internal services. Required by compose. |
| `DOT_MODEL_FILE` | GGUF file name inside `./models`. |
| `DOT_VIDEO_GID`, `DOT_RENDER_GID` | Host group ids for GPU access (`getent group video render`). |
| `DOT_WORKSPACE_DIR` | Host folder the agent works in (default `workspace`). |
| `DOT_BROWSER_TOKEN` | Needed only for `make up-browser`. |

### Models

Set `DOT_MODEL_FILE` and either `DOT_MODEL_URL` or `DOT_MODEL_REPO`, plus `DOT_MODEL_SHA256` so the download is verified, then run `make models`. `make bench` and `make gate` help you compare candidate models (see `docs/operations.md`).

### Day to day

```
make up            # start
make up-browser    # start with the browser worker (needs DOT_BROWSER_TOKEN)
make logs          # follow logs (make logs S=dot-backend)
make down          # stop
```

## Terminal client

```
uv sync --all-packages
export DOT_API_TOKEN=...      # same value as in .env
uv run dot                    # full-screen TUI
uv run dot --once "run the tests and fix failures"   # headless, prints the answer
```

See `cli/README.md`.

## Permission modes

| Mode | Behaviour |
|---|---|
| `plan` | Read-only; the agent writes a plan you approve. |
| `default` | Reads are free; edits and commands ask you. |
| `acceptEdits` | File edits inside the workspace are allowed; commands still ask. |
| `auto` | A deterministic classifier plus taint tracking decides; anything unclear asks you. |
| `bypass` | Nothing asks. Only for disposable workspaces. |

## Skills

A skill is a folder with a `SKILL.md`. Dot loads skills from `<workspace>/.dot/skills`, then `~/.dot/skills`, then the bundled `skills/` folder. The best matches are offered to the model each turn, and you can invoke one yourself by starting a message with `/skill-name`. Licensing of bundled skills is in `THIRD_PARTY.md`.

## MCP servers

Add `mcpServers` to `~/.dot/settings.json` (your own servers) or `<workspace>/.dot/settings.json` (project servers):

```json
{"mcpServers": {"docs": {"type": "http", "url": "https://example.com/mcp", "headers": {"Authorization": "Bearer ${DOCS_TOKEN}"}}}}
```

`${NAME}` only expands variables listed in `DOT_MCP_ENV_ALLOWLIST`. stdio servers run inside the sandbox. Project servers do not start until you approve them, and every MCP tool asks before it runs.

## Safety model

1. Everything the agent runs executes in a non-root container with no capabilities; only the workspace is mounted.
2. Paths are jailed to the workspace, symlinks included; Dot's own settings and hooks are read-only to the agent.
3. Every tool call passes rules (deny beats allow beats ask), hooks, the mode, and you.
4. A baseline deny list blocks reading SSH keys, cloud credentials and `.env` files.
5. Text from the web, MCP servers, workspace skills and memory is tainted; in auto mode a tainted context cannot trigger mutating calls without your approval.
6. `WebFetch` refuses private, loopback and metadata addresses and re-checks every redirect.
7. The browser worker is isolated and has its own token; an optional firewall script blocks its LAN access.
8. The API needs a bearer token, limits request size and chat rate, sets security headers and has no CORS.
9. Every decision lands in an append-only audit log.
10. Every file edit is checkpointed, so a bad turn can be rewound.

Details: `docs/architecture.md`, `docs/security.md`, `docs/operations.md`.

## Development

```
make sync
make ci          # lint, lock check, unit tests, integration smoke tests
```
