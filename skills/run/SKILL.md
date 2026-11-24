---
name: run
description: Start the project's app and check a change actually works in the running program, not just in tests. Use when asked to run, launch, start or try the app.
triggers: run app, launch, start server, try it, smoke test, see it working
---

# Run

Start the app, exercise the changed behaviour, report what you saw.

## Steps
1. Find how to run it. Read `DOT.md`, `CLAUDE.md`, `README.md`, `Makefile`, `package.json`
   scripts, `pyproject.toml` scripts. Use the documented command. Do not invent one.
2. Pick the project kind:
   - CLI: run it with a real argument and read the output.
   - Server: start it in the background with Bash (`cmd > /tmp/app.log 2>&1 &`), wait 2-5
     seconds, then call it with `curl -s -i http://127.0.0.1:<port>/<route>`.
   - Library: run a short script that imports it and calls the changed function.
   - Web UI: fetch the page with curl and check the HTML; say you cannot see it rendered.
3. Check the log for errors: `tail -30 /tmp/app.log`.
4. Exercise the change: call the exact route, command or function that was edited, with one
   normal input and one bad input.
5. Stop what you started: `kill <pid>`. Confirm the port is free.
6. Report:
   - the command you ran
   - what you sent and what came back (short excerpt)
   - pass or fail, and the error text if it failed

## Rules
- Bind servers to 127.0.0.1 only.
- Do not install system packages. If a dependency is missing, say which.
- Never claim it works without showing the real output.
- If it will not start, report the first error line and stop. Do not keep guessing.
