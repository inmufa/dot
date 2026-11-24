---
name: dot-help
description: Explain how to use Dot - modes, tools, skills, slash commands, settings and hooks. Use when asked what Dot can do or how to use a feature.
triggers: help, how do I, what can you do, commands, modes, features, getting started
---

# Dot help

Answer from this page. Keep answers short. If the question is not covered, say so.

## Modes
- `default`: reads run freely; edits and shell commands ask for approval.
- `acceptEdits`: file edits are auto-approved; shell still asks.
- `plan`: read-only. Nothing that changes files runs. Use it to plan before acting.
- `auto`: a classifier approves safe actions and asks about risky ones.
- `bypass`: no prompts. Use only in a throwaway workspace.
Change the mode in the UI mode switcher or `/mode <name>` in the TUI.

## Tools
- Read, Write, Edit: files (Read a file before changing it).
- Glob, Grep: find files and search text.
- Bash: run commands in the sandbox.
- Skill: load a skill's instructions by name.

## Skills
- A skill is a folder with `SKILL.md`. Dot suggests matching skills each turn.
- Start one yourself with `/name args`, for example `/code-review` or `/init`.
- List them: `GET /v1/skills` or `/skills` in the TUI. A skill marked unavailable names what
  is missing (a tool, an MCP server or a program).
- Add your own: `~/.dot/skills/<name>/SKILL.md` (all projects) or `.dot/skills/<name>/SKILL.md`
  (one project). Project beats user beats bundled when names clash.
- Minimal file:
```
---
name: my-skill
description: One line saying what it does and when to use it.
---
Numbered steps for the model.
```

## Built-in skills
code-review, simplify, security-review, init (creates DOT.md), loop, schedule, run,
update-config (permissions and hooks).

## Settings and hooks
`.dot/settings.json` holds permission rules and hooks. Use `/update-config` to change it.

## Sessions
`/rewind` goes back a turn, `/compact` shrinks the context, `/mcp` lists MCP servers.
The stop button or `POST /v1/sessions/{id}/stop` cancels a running turn.
