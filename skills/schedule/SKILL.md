---
name: schedule
description: Schedule a prompt to run later or on a repeating timetable, using cron and the dot headless mode. Use for "run this every day", "remind me at 9", "nightly job".
triggers: schedule, cron, nightly, daily, weekly, recurring, timer
---

# Schedule

Dot has no built-in scheduler. Use the system cron to call `dot --once "<prompt>"`.

## Steps
1. Get two things from the arguments: when, and what. If either is missing, ask one short question.
2. Convert "when" to a 5-field cron expression. Show it back in words (for example
   `0 9 * * 1-5` = weekdays at 09:00). One-off runs use `at` instead (step 6).
3. Check tools with Bash: `command -v dot crontab`. If `crontab` is missing, tell the user and stop.
   If `dot` is missing, tell the user where it should be installed and stop.
4. Write the job prompt so it works with no context: say the folder, the goal and the output
   file. Scheduled runs are headless: any action that needs approval is rejected, so only
   plan read-only work or edits that are already allowed.
5. Build the line, with the token read from an env file and never typed inline:
   `<cron> cd <workspace> && set -a && . ~/.dot/env && dot --once "<prompt>" >> ~/.dot/schedule.log 2>&1`
6. Show the exact line and ask the user to approve it before changing anything.
7. After approval, add it without removing other entries:
   `(crontab -l 2>/dev/null; echo '<line>') | crontab -`
8. Confirm with `crontab -l | tail -3`.
9. To list jobs: `crontab -l | grep 'dot --once'`. To remove one: show the matching line,
   get approval, then rewrite the crontab without that line.

## Rules
- Never put the API token in the crontab line or the prompt.
- Never schedule a prompt that deletes, pushes, sends messages or spends money.
- Always tell the user where the log is: `~/.dot/schedule.log`.
