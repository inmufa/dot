---
name: code-review
description: Review the current git diff, a branch, or named files for correctness bugs and broken project rules. Use when asked to review code, a PR, a diff or recent changes.
triggers: review, pull request, PR, diff, changes, bugs, audit code
---

# Code review

Find real bugs. Do not nitpick style.

## Steps
1. Pick the target from the arguments:
   - nothing given: `git diff HEAD` (also run `git status --short` for new files)
   - a branch: `git diff <branch>...HEAD`
   - a path: Read that file
2. If the diff is empty, say "Nothing to review." and stop.
3. For each changed file, Read the full file around the changes. A diff alone hides context.
4. Read `DOT.md` and `CLAUDE.md` in the repo root if they exist. Rules there count as findings when broken.
5. Check every change for:
   - logic errors, off-by-one, wrong condition, wrong variable
   - missing error handling on I/O, parsing, network
   - null/None/empty cases not handled
   - resource leaks (files, connections, tasks)
   - races and shared mutable state
   - new behaviour with no test
6. Verify each suspected bug before reporting it. Use Grep to find callers, or run the test
   with Bash. Drop anything you cannot back with evidence.
7. Report in this format, most severe first:

```
[high|medium|low] path:line - one-line problem
  Why: what goes wrong, with the input that triggers it.
  Fix: the smallest change.
```

8. End with one line: `N findings` or `No bugs found`.

## Rules
- Report at most 10 findings. Prefer fewer, certain ones.
- Never report formatting or naming unless a project rule requires it.
- Never edit files unless the user said "fix". If they did, apply each fix with Edit, then run
  the tests with Bash and show the result.
