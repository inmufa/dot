# Dot - project rules

Engineering playbook: `~/projects/playbook`. Rules here override it. Spec: `~/Downloads/dot_spec_v2.md`.

## Applies here
- `principles.md`, `workflow.md`
- `api/fastapi.md`, `api/errors.md`, `api/http-conventions.md`, `backend/security.md`
- `frontend/*`, `design/*` for `services/web-ui`
- `logo/*` for brand work

## Product facts
- **What it is:** self-hosted uncensored coding/research agent, Claude Code parity, local GGUF model on an RX 580 via llama.cpp Vulkan.
- **User:** one person, one workstation (i7-12700K, ~6 GB free RAM, 8 GB VRAM). Bound to 127.0.0.1.
- **Parts:** `backend` (FastAPI), `packages/dot-contracts`, `services/{sandbox-runner,browser-worker,web-ui}`, `cli` (Textual).
- **Storage:** SQLite (WAL) + FTS5 + sqlite-vec. No Postgres, Redis or Celery.
- **Error code ranges:** core 1000-1999, session 2000-2999, governance 3000-3999, tools 4000-4999. en/ru/uz.
- **Public ids:** Crockford Base32, `Letter + 5 minute chars + 4 random`.

## Overrides
- No `git worktree`, no per-branch folders (owner rule).
- Postgres/Celery/Redis rules from the playbook do not apply: single-user local tool.
- The prompt prefix must stay byte-stable. Never reorder or rewrite it between turns; compaction is the only history rewrite.

## Never
- Add a dependency without a reason in the commit.
- Put secrets in code, docs, logs or commits. `.env` is git-ignored.
- Mention AI tools in commits.
