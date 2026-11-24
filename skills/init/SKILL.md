---
name: init
description: Create DOT.md for a repository, with the commands, layout and rules an agent needs. Use when asked to init, bootstrap or document a project for Dot.
triggers: init, DOT.md, bootstrap, project instructions, onboard repo
---

# Init: write DOT.md

DOT.md is read at the start of every session. Keep it short and factual.

## Steps
1. Check for an existing `DOT.md`. If it exists, Read it and update it instead of replacing it.
   Also Read `CLAUDE.md` and `README.md` if present and reuse their facts.
2. Find the project type with Glob: `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`,
   `Makefile`, `docker-compose*.yml`, `.github/workflows/*`.
3. Read those files. Learn:
   - how to install, run, test, lint and format (exact commands)
   - the source layout: top-level folders and what each holds
   - the language version and key frameworks
4. Run the test command with Bash once, so DOT.md only lists commands that work. Note failures.
5. Find conventions: Grep config for line length, lint rules, commit style. Look at `git log -5 --oneline`.
6. Write `DOT.md` in the repo root with Write, using these sections, in this order:

```
# <project name>
<one sentence: what it is>

## Commands
- install: `...`
- run: `...`
- test: `...`
- lint: `...`

## Layout
- `path/` - what it holds

## Conventions
- rules a newcomer would break

## Do not
- things that must never be done here
```

7. Show the user the file and mention anything you could not verify.

## Rules
- Only write facts you checked in files or by running a command. No guesses.
- Maximum 80 lines. No marketing text, no progress lists.
- Never put secrets or `.env` values in it.
- Do not edit other files.
