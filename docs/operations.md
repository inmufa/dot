# Operations

Everything runs through Docker Compose (`deploy/compose/compose.base.yml` plus a GPU overlay) driven by the Makefile. `make` calls `deploy/scripts/compose.sh`, which adds the overlay for `DOT_GPU_BACKEND`; use it (or `make`) instead of bare `docker compose`. All ports are bound to 127.0.0.1.

## Install Docker

On Ubuntu: `sh deploy/scripts/install_docker.sh` (needs sudo; it installs Docker Engine from Docker's apt repo, `mesa-vulkan-drivers`, `vulkan-tools` and adds you to the `docker`, `render` and `video` groups). Log out and back in afterwards. The script is never run by make.

## GPU setup (RX 580, Vulkan)

1. `bash deploy/scripts/verify_vulkan.sh` checks `/dev/dri`, group membership, `vulkaninfo --summary` (a RADV device must be listed) and prints a docker command that proves the GPU reaches a container.
2. Put the numeric group ids it prints into `.env` as `DOT_VIDEO_GID` and `DOT_RENDER_GID` (the llama image has no host group names).
3. Run the printed `docker run ... llama-server --list-devices` command: it should name a Vulkan device with the Radeon RX 580.

## Hardware profiles

`deploy/profiles/<name>.env` holds everything that depends on the machine: llama.cpp image tag per GPU type (vulkan, cuda, rocm, cpu), `-ngl`, parallel slots, context per slot, KV cache types, flash attention, llm memory limit, projector placement (`DOT_VISION=off|cpu|gpu`), voice on/off and threads, chat rate limits.

```
make profile NAME=rx580-8gb              # validates, then writes a managed block at the end of .env
make profile NAME=rx580-8gb SET=DOT_VISION=cpu   # override a key for this run
make up
```

| Profile | Backend | Slots x ctx per slot | Notes |
|---|---|---|---|
| `rx580-8gb` | vulkan | 2 x 32768 | measured default, text-only (vision opt-in) |
| `cpu-only` | cpu | 1 x 16384 | slow, 12g RAM limit |
| `nvidia-24gb` | cuda | 4 x 65536 | needs NVIDIA Container Toolkit |
| `nvidia-48gb-multi` | cuda | 8 x 65536 | `--split-mode layer` across cards |
| `amd-rocm-16gb` | rocm | 3 x 49152 | needs `/dev/kfd` |

Only `rx580-8gb` was measured; the others are unverified starting points, so run `make bench` and `make gate` and tune. Add your own by copying a file: unknown keys, an unpinned or mismatched image tag, a quantized V cache without flash attention, `DOT_VISION=gpu` on cpu and similar mistakes are refused. `-c` is derived as slots x per-slot context. Host ids (`DOT_GPU_RENDER_NODE`, `DOT_VIDEO_GID`, `DOT_RENDER_GID`) stay in `.env` and are required for vulkan and rocm. The vulkan overlay passes only the one render node; cuda uses the NVIDIA runtime reservation. Host-specific tweaks (for example `HSA_OVERRIDE_GFX_VERSION`) go in the git-ignored `deploy/compose/compose.local.yml` (see `compose.local.example.yml`). `DOT_VOICE=on` starts the voice worker with the rest of the stack (see Voice). VRAM telemetry reads amdgpu sysfs only, so it is empty on NVIDIA.

The backend does not hardcode context. It reads `n_ctx` per slot and the slot count from llama-server `/props` at startup and every 30 s, so a bigger `-c` or more slots need no backend change (the profile values only seed it until the server answers). Compaction starts at `DOT_COMPACT_THRESHOLD` (75%) of that per-slot context; set `DOT_COMPACT_MAX_TOKENS` to compact earlier on huge contexts and `DOT_LLM_CONTEXT_CAP` to use less than the server offers. Subagent concurrency equals the slot count (restart the backend after changing slots). Raise `DOT_CHAT_RATE_PER_MIN`/`DOT_CHAT_RATE_BURST` with the slot count (profiles do). Reasoning effort levels come from `/props` of the loaded model, not from code. The prompt prefix stays byte-stable: none of this touches it.

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
| `make vault-key` / `make vault-rotate` | Create or rotate `DOT_VAULT_KEY` (see Credential vault). |
| `make init` | Create the protected `.dot` files in the workspace. |
| `make up` / `make down` | Start or stop the stack (`down` also stops the browser and voice profiles). |
| `make up-browser` | Start with the browser worker; needs `DOT_BROWSER_TOKEN` in `.env`. |
| `make up-voice` | Build and start the voice worker (and recreate the backend); needs `DOT_VOICE_TOKEN` in `.env` and the models in `models/voice`. |
| `make logs` | Follow logs, for one service with `make logs S=dot-backend`. |
| `make profile NAME=<profile>` | Apply a hardware profile to `.env`, see below. |
| `make model NAME=<model>` | Switch the model, see below. |
| `make models` | Download the model, see below. |
| `make bench` | M0 gate: llama-bench in the llm image. |
| `make gate` | M1 gate against a running llm. |

## Privacy check

`make privacy-check` (`deploy/scripts/privacy_check.sh`) tests the running stack and prints PASS or FAIL per check, exit 1 on any FAIL: container internet and DNS reachability (real connection attempts), sandbox isolation, internal networks, published ports, container hardening, `.env` mode and git status, database permissions, OpenAPI off, telemetry flags, API token absent from the web bundle, no unexpected hosts in the web bundle, and the CSP headers on `http://127.0.0.1:3000`. Run it after every `make up`. What leaves the machine and how to stop it: `docs/privacy.md`. Static compose invariants run in `uv run pytest deploy/tests`. To also block your LAN for the egress networks, read and apply `deploy/scripts/firewall_dot.sh` (it prints the rules; `--apply` needs root, `--remove` undoes it).

## Credential vault

Saved logins and browser sessions (docs/security.md "Credential vault"). Needs the browser profile (`make up-browser`).

- `make vault-key` writes `DOT_VAULT_KEY` (32 random bytes as 64 hex chars) to `.env` only if it is absent, creates the file with mode 600 and never prints the key. Then `make up` (compose passes the key to `dot-backend`). Without a key the vault is off (`GET /v1/vault/status` -> `{"enabled": false}`, other vault routes answer 4140) and everything else works.
- Back the key up with your password manager. Without it the saved logins in a database backup cannot be decrypted.
- `make vault-rotate` rotates the key: it stops `dot-backend`, copies the database inside the `dot-data` volume to `dot.db.pre-rotate-<unix time>`, re-encrypts every password, TOTP secret and session blob under a fresh key in one SQLite transaction (all or nothing), writes the new key to `.env` (mode 600) and restarts the backend. Keys travel by environment variable name only. The pre-rotate copy still needs the old key: delete it when you no longer need it.
- Backups: the vault lives in the same SQLite database (`dot-data` volume, see Backups), so a database backup holds only ciphertext; keep `.env` or the key separate from it.
- Settings (env, defaults): `DOT_VAULT_SESSION_MAX_AGE_DAYS=30`, `DOT_VAULT_SESSION_REFRESH_S=300`, `DOT_VAULT_LOGIN_RATE_PER_MIN=0.5`, `DOT_VAULT_LOGIN_BURST=3`, `DOT_VAULT_MAX_CREDENTIALS=200`.
- Browser state decision: the worker keeps one in-memory context per Dot session (no profile directory; closed after 10 idle minutes), so nothing persistent sits in the browser container. Persistence across restarts and reaping is the vault's encrypted session store, restored into a fresh context on demand. Logging in by hand in the Browser tab keeps working; use "Save this session" there to keep it.

## Voice

English speech, fully local on CPU, no network egress. Worker `dot-voice` (compose profile `voice`, internal network only): Parakeet-TDT-0.6B-v2 int8 for speech-to-text, Kokoro-82M fp32 for text-to-speech, both through sherpa-onnx. Measurements and licences: `docs/speech-gate.md`.

- Models: put them under `models/voice/` (git-ignored, mounted read-only): `parakeet-tdt-0.6b-v2-int8/` and `kokoro-multi-lang-v1_0/`. A missing model is reported by `/v1/voice/status` and the worker still serves the other half.
- Turn on: set `DOT_VOICE_TOKEN` in `.env` (`openssl rand -hex 32`), then `make up-voice`. With a hardware profile that sets `DOT_VOICE=on`, `make up` starts it too; with an empty token it stays off and says so.
- Limits: container 3 GB, `DOT_VOICE_THREADS` threads (profile), utterances over 30 s are decoded in chunks, audio over 120 s is refused. Audio and text are never stored or logged; the audit log keeps sizes only.
- Check: `curl -H "Authorization: Bearer $DOT_API_TOKEN" 127.0.0.1:8000/v1/voice/status`. The UI shows the mic and Read aloud only when the worker is up.

## Models

`make models` runs `deploy/scripts/download_models.sh`. Set in `.env`:

- `DOT_MODEL_FILE`: the file name inside `./models` (compose passes it to llama-server; `make model` sets it).
- one source: `DOT_MODEL_URL` (direct link, curl) or `DOT_MODEL_REPO` (`OWNER/REPO` on Hugging Face; uses `huggingface-cli` when installed, else curl).
- `DOT_MODEL_SHA256`: the expected hash. When set, the file is verified and deleted on mismatch. Without it the script prints the computed hash so you can record it.

Flags `--repo`, `--file`, `--url`, `--sha256` override `.env` (`make models ARGS="--sha256 ..."`).

### Model registry and switching

`models/registry.toml` (tracked, the rest of `models/` is git-ignored) describes each GGUF: `file`, `name`, `mmproj`, `context_max`, `thinking`, `effort_levels`, `recommended_profile`. `GET /v1/models` lists every `*.gguf` in `./models` (mounted read-only into the backend) merged with it: `display_name`, `listed`, `vision` (true only when the entry names an `mmproj` that exists), `context_max`, `thinking`, `effort_levels`, `recommended_profile`. A file without an entry still works and is shown as unlisted with no effort levels and no vision. A missing or broken registry is ignored. Adding a model is: drop the GGUF (and projector) in `./models`, add a `[[model]]` block, `make model NAME=...`. No code edits. `GET /v1/telemetry` shows the loaded model, slots, speed and VRAM (`DOT_VRAM_SYSFS_DIR` in `.env` is the dGPU's sysfs device folder, mounted read-only).

To switch: `make model NAME=<file, stem or registry name>`. It sets `DOT_MODEL_FILE`, re-derives the projector and context clamp (`context_max`) from the applied profile, recreates `dot-llm` (about a minute; running turns fail) and the backend if its env changed. Without a profile applied it only sets the file. `POST /v1/models/select` (the UI) always answers 501; `GET /v1/models` gives each file a `switch_command` for the UI to show. The backend has no docker socket, so it cannot recreate the container itself. llama.cpp router mode (`--models-dir`, `--models-max 1`) exists in the pinned image but was not adopted: it changes `/props`, `model` routing and per-model projector/context args for every client, needs a generated preset, and could not be tested without taking the live dot-llm down. A host-side helper was rejected on purpose.

Router mode needs `--models-dir /models --models-max 1` on `dot-llm`, which also changes how `--parallel`/`-c` apply per model. Try it on a spare port first; if the model plus its cache no longer fits in VRAM, stay with `make model`.

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
