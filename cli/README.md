# dot (terminal client)

A Textual TUI for the Dot backend. It talks to the same HTTP API as the web UI.

## Install and run

From the repository root:

```
uv sync --all-packages
uv run dot
```

The backend must be running (`make up`).

## Options

| Flag | Environment | Default | Meaning |
|---|---|---|---|
| `--url` | `DOT_URL` | `http://127.0.0.1:8000` | Backend address. |
| `--token` | `DOT_API_TOKEN` | none | Bearer token (same as the backend's). |
| `--session` | `DOT_SESSION` | new session | Resume a session by id. |
| `--mode` | | session default | `plan`, `default`, `acceptEdits`, `auto` or `bypass`. |
| `--once MESSAGE` | | | Headless: run one turn, print the final answer to stdout. |

## Slash commands

`/mode <name>` switch permission mode, `/stop` cancel the running turn, `/new` start a new session, `/help`, `/quit`. A message starting with `/skill-name` invokes a skill.

When the agent asks for approval, press `a` to allow, `s` to allow for the session, `r` to reject. Questions from `AskUserQuestion` are shown as notices; answer them in the web UI.

## Headless mode

```
uv run dot --once "summarise the failing tests" --mode plan
```

Only the text after the last tool call is printed. Approvals are rejected automatically and questions are answered with "no user available", so a turn never hangs; use `--mode acceptEdits` or an allow rule for unattended edits. Errors go to stderr and the exit code is 1.
