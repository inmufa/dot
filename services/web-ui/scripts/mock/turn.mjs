// Turn engine: streams one assistant turn as SSE, records it for history, dispatches scenarios.
import { st, nid, sleep, add, persistTurn, SLOW, EFFORTS } from "./core.mjs";
import { scenario } from "../mock-scenarios.mjs";

const DIFF = `--- a/src/app.py
+++ b/src/app.py
@@ -10,7 +10,8 @@ def main():
     args = parse()
-    run(args)
+    setup_logging(args.verbose)
+    run(args)
     return 0
`;
const LONG_UNBROKEN = "x".repeat(6000);
const WORDS = "consider the request then weigh options check constraints compare approaches verify edge cases plan next step".split(" ");

export async function turn(s, text, res, body = {}, opts = {}) {
  const send = (e) => !res.writableEnded && res.write(`data: ${JSON.stringify(e)}\n\n`);
  const effort = EFFORTS.includes(body.effort) ? body.effort : s.effort ?? "medium";
  const ultra = effort === "max" || /ultrathink/i.test(text);
  const acc = { text: "", thinking: "", calls: [], widgets: [], sources: null, effort };
  const atts = (Array.isArray(body.attachments) ? body.attachments : []).map((a) => st.uploads.get(s.id)?.get(a)).filter(Boolean);

  const tok = async (t, thinking = false) => {
    if (thinking && effort === "off") return;
    for (const part of t.match(t.length > 500 ? /[\s\S]{1,400}/g : /[\s\S]{1,12}/g) ?? []) {
      if (s.cancel) return;
      send({ type: "token", text: part, thinking });
      acc[thinking ? "thinking" : "text"] += part;
      await sleep(SLOW);
    }
  };
  /** Thinking tokens for `ms` at 25 ms ticks; skipped when effort is off. */
  const thinkFor = async (ms) => {
    if (effort === "off") return;
    const end = Date.now() + ms;
    for (let i = 0; Date.now() < end && !s.cancel; i++) {
      const w = `${WORDS[i % WORDS.length]} `;
      send({ type: "token", text: w, thinking: true });
      acc.thinking += w;
      await sleep(25);
    }
  };
  const block = async (p) => { s.blocked++; try { return await p; } finally { s.blocked--; } };
  const approve = (approval_id) => block(new Promise((r) => st.approvals.set(approval_id, r)));
  const usage = (k) => send({ type: "usage", context_tokens: 1200 * k, context_limit: 16384 });
  const record = (call_id, name, args, r) => acc.calls.push({ call_id, name, args, output: r?.output, tainted: r?.tainted });

  const tool = async (name, args, output, ask, tainted = false) => {
    const call_id = `call_${nid()}`;
    const mk = (extra) => st.audit.unshift({ id: `A${st.n}`, session: s.id, mode: s.mode, tool: name, args, created_at: new Date().toISOString(), ...extra });
    send({ type: "tool_call", invocation: { call_id, name, arguments: args } });
    mk({ decision: ask ? "ask" : "allow", source: ask ? "classifier" : "rule", reason: ask ? "mutating call" : "read-only" });
    if (ask) {
      const approval_id = `ap_${st.n}`;
      send({ type: "approval_required", approval_id, invocation: { call_id, name, arguments: args }, diff: ask.diff ?? null, verdict: { decision: "ask", stage: "B", reason: ask.reason } });
      const decision = await approve(approval_id);
      mk({ id: `U${st.n}`, decision: decision === "reject" ? "deny" : "allow", source: "user", reason: `answered ${decision}` });
      if (decision === "reject") {
        const out = "Denied (error 3000): rejected by user";
        send({ type: "tool_result", result: { call_id, output: out, is_error: true, tainted: false, spill_path: null } });
        record(call_id, name, args, { output: out });
        return false;
      }
    }
    send({ type: "tool_result", result: { call_id, output, is_error: false, tainted, spill_path: null } });
    record(call_id, name, args, { output, tainted });
    return true;
  };

  /** Emit a Present tool call plus its `widget` event; props are persisted in the stored tool call. */
  const present = async (kind, title, props) => {
    const call_id = `call_${nid()}`;
    const output = `Displayed ${kind} widget`;
    send({ type: "tool_call", invocation: { call_id, name: "Present", arguments: { kind, title } } });
    send({ type: "widget", call_id, kind, title, props });
    send({ type: "tool_result", result: { call_id, output, is_error: false, tainted: false, spill_path: null } });
    record(call_id, "Present", { kind, title, props }, { output });
    acc.widgets.push({ call_id, kind, title, props });
    await sleep(SLOW * 3);
  };

  if (!opts.regen) add(s, { role: "user", content: text, ...(atts.length ? { meta: { attachments: atts.map(({ id, name, mime, size, kind }) => ({ id, name, mime, size, kind })) } } : {}) });
  if (!s.title) s.title = text.slice(0, 60);
  usage(1);
  if (atts.length) await tok(`Received ${atts.length} attachment(s): ${atts.map((a) => `${a.name} (${a.kind}, ${a.size} B)`).join(", ")}.\n\n`);
  if (ultra && !/think/i.test(text)) await thinkFor(4000 + Math.random() * 4000);

  const c = { s, send, tok, tool, usage, sleep, answers: st.answers, approve, block, thinkFor, present, effort, ultra, body, acc, id: nid, add: (m) => add(s, m) };
  if (await scenario(text, c)) {
    /* handled by a scenario */
  } else if (/long/i.test(text)) {
    await tok("Worst case output follows.\n\n" + LONG_UNBROKEN + "\n\nعربي نص طويل للاختبار 🙂 Привет, мир! Oʻzbekcha: gʻoya, oʻrik.\n");
    await tool("Bash", { command: "cat big.log " + LONG_UNBROKEN.slice(0, 300) }, Array.from({ length: 400 }, (_, i) => `line ${i} ${"y".repeat(60)}`).join("\n") + "\n" + LONG_UNBROKEN);
  } else if (/code/i.test(text)) {
    await tok("Here is a **fix**:\n\n```python\ndef add(a: int, b: int) -> int:\n    return a + b  # simple\n```\n\n- first point with `inline code`\n- second point\n\n| name | value |\n|---|---|\n| alpha | 1 |\n| beta | 2 |\n\nSee [docs](https://example.com).");
  } else if (/edit|bash/i.test(text)) {
    await tok("I need to change a file.", true);
    await tok("Let me update the entry point.");
    usage(2);
    const edit = /edit/i.test(text);
    const ok = await tool(edit ? "Edit" : "Bash", edit ? { file_path: "src/app.py", old: "run(args)", new: "setup_logging(args.verbose)\nrun(args)" } : { command: "rm -rf build && npm run build" }, edit ? "Edited src/app.py (1 replacement)" : "build ok", edit ? { diff: DIFF, reason: "edits a tracked file" } : { reason: "destructive shell command" });
    if (!s.cancel) await tok(ok ? "Done. The entry point now configures logging." : "Understood, I left the file alone.");
  } else {
    await tok("The user wants a summary. I should read the readme first.", true);
    await tok("Reading the project overview.\n");
    usage(2);
    await tool("Read", { file_path: "README.md" }, "     1\t# Dot\n     2\tSelf-hosted coding agent.");
    await tok("Dot is a self-hosted coding and research agent.");
  }
  persistTurn(s, acc);
  s.state = "idle";
  usage(3);
  send({ type: "done", stop_reason: s.cancel ? "cancelled" : "end_turn" });
  res.end();
}
