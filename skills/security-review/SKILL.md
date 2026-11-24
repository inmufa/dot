---
name: security-review
description: Security review of pending changes or named files. Finds injection, auth gaps, secrets, unsafe deserialization and path traversal. Use when asked for a security review or audit.
triggers: security, vulnerability, injection, xss, secrets, auth, traversal, owasp
---

# Security review

Report only issues that an attacker can actually reach.

## Steps
1. Target: `git diff HEAD` by default, or the path/branch in the arguments. If empty, say so and stop.
2. For every changed file, Read it fully. Find where untrusted input enters: HTTP params,
   request bodies, headers, CLI args, files, env, model or tool output.
3. Follow each input to where it is used. Flag it when it reaches:
   - SQL built with string formatting (needs parameters)
   - a shell command (`shell=True`, `os.system`, backticks) without quoting
   - a file path without a check that the resolved path stays inside the allowed root
   - HTML output without escaping (XSS)
   - `eval`, `exec`, `pickle.loads`, `yaml.load` (unsafe load), `subprocess` with user text
   - an outgoing URL fetch with a user URL (SSRF)
4. Check auth: every new route needs the token/permission check the other routes use. Grep for it.
5. Check secrets: Grep the diff for `password`, `secret`, `token`, `api_key`, `BEGIN PRIVATE KEY`,
   long random-looking strings. Secrets must never be in code, logs or error messages.
6. Check new dependencies: name them and note anything unpinned or unmaintained.
7. Confirm each finding by tracing the exact path from input to sink. Drop what you cannot trace.

## Report format
```
[critical|high|medium|low] path:line - vulnerability name
  Attack: how input reaches the sink.
  Fix: the concrete change.
```
End with `N findings` or `No exploitable issues found`.

## Rules
- Do not run exploits or touch real services.
- Do not edit files unless the user said "fix".
- Never print a secret value; give only file and line.
