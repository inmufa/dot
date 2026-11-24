# Operations

Everything runs through Docker Compose (`deploy/compose/compose.base.yml`) driven by the Makefile. All ports are bound to 127.0.0.1.

## Install Docker

On Ubuntu: `sh deploy/scripts/install_docker.sh` (needs sudo; it installs Docker Engine from Docker's apt repo, `mesa-vulkan-drivers`, `vulkan-tools` and adds you to the `docker`, `render` and `video` groups). Log out and back in afterwards. The script is never run by make.

## GPU setup (RX 580, Vulkan)

1. `bash deploy/scripts/verify_vulkan.sh` checks `/dev/dri`, group membership, `vulkaninfo --summary` (a RADV device must be listed) and prints a docker command that proves the GPU reaches a container.
2. Put the numeric group ids it prints into `.env` as `DOT_VIDEO_GID` and `DOT_RENDER_GID` (the llama image has no host group names).
3. Run the printed `docker run ... llama-server --list-devices` command: it should name a Vulkan device with the Radeon RX 580.

## First start

```
cp .env.example .env      # then edit the tokens, see below
mkdir -p workspace models
make init                 # creates workspace/.dot/settings.json and .dot/hooks
make models               # fetch the GGUF (see below)
make up
```

Generate secrets with `openssl rand -hex 32` for `DOT_API_TOKEN`, `DOT_SANDBOX_TOKEN` and `SEARXNG_SECRET` (compose refuses to start without them). The web UI is at http://127.0.0.1:3000. Check readiness with `curl -s http://127.0.0.1:8000/ready`.

## Make targets

| Target | What it does |
|---|---|
| `make sync` | Install all Python packages and dev tools with uv. |
| `make lint` / `make fmt` | ruff check and format check / apply fixes. |
| `make test` | Unit tests of each package separately (backend without integration, sandbox, browser worker, cli, deploy). |
| `make integration` | Real-protocol smoke tests: fake llama-server over HTTP, real sandbox process, real SQLite. |
| `make lockcheck` | `uv lock --check`. |
| `make ci` | lint, lockcheck, test, integration (what GitHub Actions runs, minus the web UI and docker build jobs). |
| `make init` | Create the protected `.dot` files in the workspace. |
| `make up` / `make down` | Start or stop the stack (`down` also stops the browser profile). |
| `make up-browser` | Start with the browser worker; needs `DOT_BROWSER_TOKEN` in `.env`. |
| `make logs` | Follow logs, for one service with `make logs S=dot-backend`. |
| `make models` | Download the model, see below. |
| `make bench` | M0 gate: llama-bench in the llm image. |
| `make gate` | M1 gate against a running llm. |

## Models

`make models` runs `deploy/scripts/download_models.sh`. Set in `.env`:

- `DOT_MODEL_FILE`: the file name inside `./models` (compose passes it to llama-server).
- one source: `DOT_MODEL_URL` (direct link, curl) or `DOT_MODEL_REPO` (`OWNER/REPO` on Hugging Face; uses `huggingface-cli` when installed, else curl).
- `DOT_MODEL_SHA256`: the expected hash. When set, the file is verified and deleted on mismatch. Without it the script prints the computed hash so you can record it.

Flags `--repo`, `--file`, `--url`, `--sha256` override `.env` (`make models ARGS="--sha256 ..."`).

## M0 and M1 gates (choosing the model)

1. `make bench` (needs docker and the model) prints a llama-bench table from inside the `dot-llm` image and the steps for the native comparison. Native and docker numbers should be close; a large gap points at the container GPU setup.
2. `make up` and wait until `dot-llm` is healthy, then `make gate` (same as `uv run deploy/scripts/m1_model_gate.py --base-url http://127.0.0.1:8080/v1`). It runs 20 scripted tool-call tasks and a 10-turn prefix-reuse probe, prints markdown tables and exits non-zero if tool-call success is under 90% or median prompt reuse from turn 2 on is under 80%.
3. Check the llama-server log for full re-processing too (see Troubleshooting). Pick the model that passes, set `DOT_MODEL_FILE`.

### Thinking and sampling

`DOT_LLM_THINKING=on|off|auto` (`auto` leaves the chat template default), `DOT_LLM_TEMPERATURE`, `DOT_LLM_TOP_P`, `DOT_LLM_TOP_K`, `DOT_LLM_PRESENCE_PENALTY` (defaults 0.6 / 0.95 / 20 / 0) are sent with every streamed request; `DOT_LLM_DEBUG_FILE` appends each request body as JSONL (replay it against llama-server to debug). The gate takes the same knobs: `--no-think --temperature 0.7 --top-p 0.8 --presence-penalty 1.5`.

Why thinking stays on and reasoning is stored: Qwen3.5 sometimes ends a reply inside `<think>` without closing it, so the answer lands only in `reasoning_content`. Replaying past assistant turns with an empty think block made that happen in 4-8 of 10 post-tool replies; replaying the real reasoning (`messages.reasoning`, sent back as `reasoning_content`) brought it to 0 of 12. As a safety net, an empty reply (no text, no tool calls) gets one `<system-reminder>` nudge appended as a user row; if still empty, the tail of the reasoning becomes the visible answer (`meta.reasoning_promoted`).

`make gate` tool-call success on the 9B model is noisy between runs (80-90%, failures are mostly Bash vs Glob choices), so it does not discriminate between the sampling settings.

Opt-in check against the real model through the public API (not part of CI): `DOT_API_TOKEN=... uv run deploy/scripts/smoke_real.py -n 10` (exit 1 above 10% empty final answers).

## Backups

State lives in two named volumes (Compose project `dot`) and the workspace folder.

```
mkdir -p backups
docker run --rm -v dot_dot-data:/data:ro -v "$PWD/backups:/backup" alpine \
  tar czf /backup/dot-data-$(date +%F).tar.gz -C /data .
docker run --rm -v dot_dot-memory:/memory:ro -v "$PWD/backups:/backup" alpine \
  tar czf /backup/dot-memory-$(date +%F).tar.gz -C /memory .
```

For a consistent SQLite copy run `make down` first. Restore into an empty volume with the reverse command (`tar xzf ... -C /data`, volume mounted without `:ro`). Back up the workspace folder with your normal tools (it is a plain host directory). `.env` holds the tokens; keep a copy somewhere private.

## Upgrade

```
git pull
make down
docker compose --env-file .env -f deploy/compose/compose.base.yml build
make up
```

`make up` alone does not rebuild images that already exist, so run the `build` line after pulling. Pinned images (llama.cpp, SearXNG) change only when you edit their tags in the compose file. Back up the volumes before upgrading.

## Startup errors

The backend validates its configuration before serving. A missing or placeholder `DOT_API_TOKEN`, an unwritable `DOT_DB_PATH` or `DOT_MEMORY_DIR`, a `DOT_WORKSPACE` that is not a directory, a missing rules file, an unknown `DOT_TIMEZONE` or a non-numeric limit prints one line per problem on stderr and exits with status 2 (no traceback). `make logs S=dot-backend` shows it; fix `.env` and run `make up` again.

## Health and readiness

- `/health` is liveness: the process answers.
- `/ready` is readiness: 200 only when SQLite, the sandbox `/health` and llama-server `/health` all answer; otherwise 503 with code 1008 and `Retry-After: 5`, and the backend log names the failing dependency. The browser worker, SearXNG and MCP servers never affect it.

Shutdown on `docker compose down` cancels running turns, stops the scheduler and MCP connections, and closes the database.

## Troubleshooting

**`/ready` returns 503.** Read `make logs S=dot-backend` for the failing dependency. The model takes up to a minute to load (`dot-llm` healthcheck has a 60 s start period); `docker compose ... ps` shows its health.

**llama-server fails to start or runs on the CPU.** Run `verify_vulkan.sh`. Typical causes: user not in `render`/`video`, wrong `DOT_VIDEO_GID`/`DOT_RENDER_GID`, `mesa-vulkan-drivers` missing, only `llvmpipe` listed. Bisect by removing `cap_drop` and `no-new-privileges` from the `dot-llm` service temporarily. If the model does not fit in 8 GB of VRAM, lower `-c` or `-ngl` in the compose command and set `DOT_LLM_CONTEXT_LIMIT` to the per-slot context (`-c` divided by `--parallel`).

**Every agent step takes tens of seconds (prompt cache not reused).** Some recurrent or hybrid models make llama.cpp re-process the whole prompt each turn. To check, start llama-server with verbose logging, for example through a compose override file that adds `LLAMA_ARG_LOG_VERBOSITY: "4"` (trace) to the `dot-llm` environment, run a few turns and search the log:

```
make logs S=dot-llm | grep -i "forcing full prompt re-processing"
```

The line "forcing full prompt re-processing due to lack of cache data" means the prefix was not reused. You can also read the `timings` of a response: `cache_n` is the number of reused prompt tokens and `prompt_n` the number processed; on turn 2 and later `prompt_n` should be small and `cache_n` large (`make gate` reports this per turn). Remedies: a newer llama.cpp image tag, a different model, tuning `--ctx-checkpoints`. Also make sure nothing rewrites the prompt prefix (custom global rules that change between turns, compaction firing every turn).

**Chat returns 429 (code 1004).** The chat start rate limit was hit; wait for `Retry-After` seconds or raise `DOT_CHAT_RATE_PER_MIN` and `DOT_CHAT_RATE_BURST`.

**413 (codes 1010, 1011).** The message or request body exceeds `DOT_MAX_MESSAGE_CHARS` or `DOT_MAX_BODY_BYTES`.

**Sandbox cannot write the workspace.** The host directory must be owned by uid 1000. `mkdir` it yourself before the first `make up`, otherwise Docker creates it as root.

**`make up-browser` refuses to start.** Set `DOT_BROWSER_TOKEN` in `.env`.

**Web UI shows offline.** Check that `dot-backend` is healthy and that `DOT_API_TOKEN` in `.env` is the one the backend started with (restart after changing it).
