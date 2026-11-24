---
name: loop
description: Repeat a task or poll a condition several times in this turn, with a wait between rounds, until it succeeds or a limit is reached. Use for "keep trying", "check every N seconds", "run until it passes".
triggers: loop, repeat, poll, retry, until, keep checking, every minutes
---

# Loop

Usage: `/loop [interval] [max=N] <task>`  Example: `/loop 30s max=10 check if the build passed`

## Steps
1. Parse the arguments:
   - interval: a number plus `s` or `m`. Default 30s.
   - `max=N`: default 10, hard cap 30.
   - the rest is the task. If the task is empty, ask what to repeat and stop.
2. Define the stop condition in one sentence (for example "tests exit 0"). If the task has no
   clear end, use "the task reports it is done".
3. Run round 1: do the task with your normal tools.
4. After each round print one line: `round i/N: <result in a few words>`.
5. If the stop condition is met, stop and give the final result.
6. Otherwise wait with Bash: `sleep <seconds>`. Then do the next round.
7. If the same failure repeats 3 rounds in a row, stop and explain. Do not keep retrying blindly.
8. When max rounds is reached, stop and say the condition was not met, with the last result.

## Rules
- Each round must be cheap. Re-run the single check, not the whole task.
- Never change files in a round unless the task says to. A polling loop only reads.
- Never run a loop that sends messages, spends money or deletes data without approval each round.
- For work that must continue after this chat ends, use `/schedule` instead.
