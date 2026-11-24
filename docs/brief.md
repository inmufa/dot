# Dot - brief

## What & who
Self-hosted autonomous engineering and research agent for one developer on one Ubuntu workstation. Runs a local uncensored GGUF model through llama.cpp (Vulkan, RX 580) inside a deterministic harness that mirrors Claude Code: tools, permission modes, hooks, skills, subagents, MCP, compaction, checkpoints.

## Parts
| Part | Stack | Users | Notes |
|---|---|---|---|
| backend | FastAPI, Python 3.12, SQLite | web + TUI | agent loop, governance, context, skills, MCP client |
| dot-contracts | Pydantic v2 | all Python parts | shared DTOs and SSE events |
| sandbox-runner | FastAPI, non-root container | backend | only writer of /workspace |
| browser-worker | Playwright | backend | on-demand profile |
| web-ui | Next.js | owner | cockpit |
| cli | Textual | owner | same API |
| dot-llm | llama.cpp server-vulkan | backend | pinned image |
| dot-searxng | SearXNG | backend | JSON search |

## Domain
Entities: session, message, task (DAG), memory chunk, checkpoint, audit entry, approval.
State machines: tool call = proposed -> (approved | denied) -> running -> done | error; session turn = idle -> running -> awaiting_approval -> running -> idle.
Tenancy: none (single user).

## Roles & auth
One local user; bearer token from `.env`; loopback only.

## Money / Integrations / Jobs
Money: none. Integrations: MCP servers, SearXNG. Jobs: asyncio scheduler (cron tool, memory consolidation, log cleanup). No Celery.

## Languages
UI en; API errors en/ru/uz (default en).

## Design direction
Subject: a quiet workshop terminal. Mood: precise, calm, technical. Palette and type decided in the brand phase. Memorable thing: a single dot as the live state indicator (idle, thinking, waiting for approval).

## Environments
Local only. No prod domain.

## Scale
One user, at most 2 concurrent model slots, 32k context.

## Defaults assumed
Local API token only; no cloud LLM fallback; workspace is a host folder mounted at /workspace.

## First milestone
Dot fixes a failing test in a sample repo through the API and TUI, with approvals.
