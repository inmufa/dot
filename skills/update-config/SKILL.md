---
name: update-config
description: Safely edit .dot/settings.json permission rules and hooks. Use when asked to allow or deny a tool, add a permission, or add a hook that runs on events.
triggers: settings, permissions, allow, deny, hook, config, settings.json
---

# Update config

Settings live in `.dot/settings.json` (workspace) and `~/.dot/settings.json` (user).
Workspace overrides user. Writing under `.dot/` is protected: show the final JSON to the
user and let them apply it, or use Bash only if they approve.

## Steps
1. Decide the scope. Default is the workspace file. Use the user file only if asked ("globally").
2. Read the current file. If it does not exist, start from `{}`.
3. Make the edit in your head, then print the full resulting JSON.
4. Validate: the JSON must parse. Check with Bash:
   `python3 -c "import json,sys; json.load(open(sys.argv[1]))" <file>`
5. Show a diff of the change (old lines with `-`, new with `+`) and ask for approval.
6. Apply after approval. Re-run step 4 on the file.

## Permission rules
```json
{"permissions": {"allow": ["Bash(git status)", "Read"], "deny": ["Bash(rm *)"], "ask": ["Write"]}}
```
- Rule form: `ToolName` or `ToolName(pattern)`.
- Add to the right list; never duplicate an entry; keep existing entries.
- Prefer the narrowest rule. Allow `Bash(git status)`, not `Bash`.
- Never allow `Bash(*)` or broad `rm`, `curl | sh`, `sudo`. Refuse and explain.

## Hooks
```json
{"hooks": {"PostToolUse": [{"matcher": "Edit", "command": "ruff format $FILE"}]}}
```
- Events: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Notification, Stop,
  SubagentStop, PreCompact.
- The command runs in the sandbox and gets JSON on stdin.
- Keep hook commands fast and read-only unless the user asks for more.
- Explain in one line what the hook will do before adding it.

## Rules
- Never remove or rewrite entries the user did not mention.
- Never add secrets to settings files.
- If the request is unclear, ask one question.
