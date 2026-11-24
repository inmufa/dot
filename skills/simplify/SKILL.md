---
name: simplify
description: Clean up changed code for reuse, simplicity and efficiency, then apply the fixes. Use when asked to simplify, tidy, refactor or clean recent changes.
triggers: simplify, cleanup, refactor, tidy, duplicate, reuse, dead code
---

# Simplify

Make the changed code smaller and clearer without changing behaviour.

## Steps
1. Get the changes: `git diff HEAD` and `git status --short`. If a path was given, use that
   file instead. If nothing changed, say "Nothing to simplify." and stop.
2. Run the tests first with Bash and note the result. If there are no tests, say so.
3. Read each changed file in full.
4. Look for these, in order:
   - duplicated code that an existing helper already covers (Grep for the helper first)
   - code copied twice inside the diff: merge into one function
   - dead code: unused variables, imports, branches that cannot run
   - needless nesting: use early returns
   - needless abstraction: a class or wrapper used once
   - slow patterns: repeated work inside loops, repeated file reads, N+1 calls
   - comments that restate the code: delete them
5. Apply each fix with Edit. One small change at a time.
6. Run the tests again with Bash. If anything broke, undo that edit and move on.
7. Report: a short list of what changed, then the test result before and after.

## Rules
- Behaviour must stay identical. No new features.
- Touch only the changed code and its direct helpers.
- Do not rename public functions or change signatures other files use.
- If a change is a matter of taste, skip it.
