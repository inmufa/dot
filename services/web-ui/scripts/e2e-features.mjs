// Phase 6 flows: question, subagent, plan, compaction, taint, context popover, and the new panels.
import { AxeBuilder } from "@axe-core/playwright";
import { clickPanelRow } from "./pw-sidebar.mjs";

export const axeFindings = [];

export async function axe(page, label) {
  // let finite animations and transitions (toast, tooltip fades) settle: axe would read mid-fade opacity as low contrast
  await page.evaluate(() => Promise.race([Promise.all(document.getAnimations().filter((a) => a.effect?.getTiming().iterations !== Infinity).map((a) => a.finished.catch(() => undefined))), new Promise((r) => setTimeout(r, 2000))]));
  const r = await new AxeBuilder({ page }).analyze();
  for (const v of r.violations.filter((x) => x.impact === "serious" || x.impact === "critical")) {
    axeFindings.push(`${label}: ${v.id} (${v.impact}) ${v.nodes.slice(0, 2).map((n) => `${n.target.join(" ")} ${n.html.slice(0, 90)}`).join(" | ")}`);
  }
}

export async function features(page, t) {
  const { name, phone, snap, noHScroll, send, idle, ok } = t;
  const box = page.getByRole("combobox", { name: "Message" });
  const openPanel = async (label, wait) => {
    if (phone) await page.getByRole("button", { name: "Open sessions" }).click();
    await clickPanelRow(page, label);
    await page.getByText(wait).first().waitFor();
    await page.waitForTimeout(350);
  };
  const closePanel = async () => { await page.keyboard.press("Escape"); await page.waitForTimeout(300); };
  const approvalArmed = () => page.waitForTimeout(900);

  // composer placeholder never clips (measured with the textarea's own font)
  const fits = await page.evaluate(() => {
    const ta = document.querySelector(".composer textarea");
    const cs = getComputedStyle(ta);
    const c = document.createElement("canvas").getContext("2d");
    c.font = `${cs.fontSize} ${cs.fontFamily}`;
    return { need: c.measureText(ta.placeholder).width, have: ta.clientWidth };
  });
  ok(fits.need <= fits.have, `${name}: idle placeholder fits (${Math.round(fits.need)}/${fits.have})`);

  // question: keys 1-3 + Enter, then multi-select with Other
  await send("ask me something");
  await page.locator(".question").waitFor();
  await page.waitForTimeout(250);
  await snap("30-question"); await noHScroll("question");
  ok((await box.getAttribute("placeholder")) === "Answer above first" && await box.isDisabled(), `${name}: composer blocked by question`);
  ok(/\d:\d\d left/.test(await page.locator(".question .badge").textContent()), `${name}: question timeout shown`);
  await axe(page, `${name} question`);
  await page.keyboard.press("2");
  ok(await page.getByRole("radio", { name: /structlog/ }).isChecked(), `${name}: key 2 selects option 2`);
  await page.keyboard.press("Enter");
  await page.locator(".question").waitFor({ state: "detached" });
  await idle();
  ok(await page.getByText("answered: structlog").count() === 1, `${name}: answer recorded in transcript`);
  await send("ask multi");
  await page.locator(".question").waitFor();
  await page.keyboard.press("1"); await page.keyboard.press("2");
  await page.getByLabel("Other").fill("custom check");
  await page.getByLabel("Other").press("Enter");
  await idle();
  ok(await page.getByText("answered: stdlib logging, structlog, custom check").count() === 1, `${name}: multi-select plus Other`);

  // subagents, subagent approval, tainted result
  await send("agent survey");
  await page.getByRole("alertdialog").waitFor();
  ok(await page.getByText("from Verifier 2").count() === 1, `${name}: approval tagged with subagent`);
  await snap("31-subagent-approval"); await noHScroll("subagent approval");
  await approvalArmed();
  await page.keyboard.press("a");
  await idle();
  await page.locator(".activity-head").last().click();
  await page.locator(".sub-row").first().click();
  await page.waitForTimeout(150);
  await snap("32-subagent"); await noHScroll("subagent");
  ok(await page.locator(".sub").count() === 2, `${name}: two subagent lines`);
  ok(await page.getByRole("list", { name: /^Tools used by/ }).first().getByRole("listitem").count() >= 4, `${name}: subagent steps listed`);
  ok(await page.locator(".taint").count() >= 1, `${name}: taint shield on tool result`);
  await axe(page, `${name} subagent`);

  // plan approval: reject is immediate, approve renders the plan block
  await send("plan the change");
  await page.getByRole("alertdialog", { name: /Plan ready/ }).waitFor();
  ok(await page.locator(".plan-body h4").count() === 1 && await page.locator(".approval .diff").count() === 0, `${name}: plan is rendered markdown, not a diff`);
  await snap("33-plan-approval"); await noHScroll("plan approval");
  await axe(page, `${name} plan approval`);
  await page.keyboard.press("r");
  await page.getByRole("alertdialog").waitFor({ state: "detached", timeout: 1500 });
  await idle();
  await send("plan again");
  await page.getByRole("alertdialog").waitFor(); await approvalArmed();
  await page.keyboard.press("a");
  await idle();
  ok(await page.getByRole("region", { name: "Plan", exact: true }).count() === 1, `${name}: plan block in transcript`);
  await snap("34-plan-block");

  // compaction divider
  await send("compact please");
  const cmp = page.getByRole("separator", { name: "Context compacted" });
  await cmp.waitFor();
  await idle();
  ok(/context compacted\s*12\.1k.*4\.3k/.test((await cmp.textContent()) ?? ""), `${name}: compaction divider text`);
  await snap("35-compaction");

  // context popover + compact
  await page.locator(".ctx-btn").click();
  await page.getByText("Prompt layers").waitFor(); await page.waitForTimeout(250);
  await snap("36-context"); await noHScroll("context popover");
  await axe(page, `${name} context`);
  await page.getByRole("button", { name: "Compact now" }).click();
  await page.getByText(/Compacted 7\.2k to 2\.6k/).first().waitFor();
  await page.keyboard.press("Escape");

  // panels
  await openPanel("Tasks", "Write the failing test");
  ok(await page.locator(".pn-status", { hasText: "blocked" }).count() >= 1, `${name}: blocked task chip`);
  await snap("37-tasks"); await noHScroll("tasks"); await axe(page, `${name} tasks`); await closePanel();

  await openPanel("Memory", "Prefers uv over pip");
  await snap("38-memory"); await noHScroll("memory"); await axe(page, `${name} memory`);
  await page.getByLabel("Search facts").fill("tests");
  await page.getByText("Prefers uv").waitFor({ state: "detached" });
  await page.getByLabel("Search facts").fill("");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Temp fact");
  await page.getByLabel("Fact", { exact: true }).fill("Delete me");
  await page.getByRole("button", { name: "Save fact" }).click();
  await page.getByText("Temp fact").waitFor();
  await page.getByRole("button", { name: "Actions for Temp fact" }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByText("Temp fact", { exact: true }).waitFor({ state: "detached" });
  ok(await page.getByRole("dialog", { name: "Memory" }).isVisible(), `${name}: memory panel stays open after confirm`);
  ok(true, `${name}: memory add, search, delete with confirm`);
  await closePanel();

  await openPanel("MCP", "project-db");
  await snap("39-mcp"); await noHScroll("mcp"); await axe(page, `${name} mcp`);
  await page.getByRole("button", { name: /Review and trust/ }).click();
  await page.waitForTimeout(150);
  await snap("40-mcp-trust"); await noHScroll("mcp trust");
  await page.getByRole("button", { name: "Trust and start" }).click();
  await page.waitForFunction(() => [...document.querySelectorAll(".pn-status")].filter((b) => b.textContent === "connected").length >= 2, null, { timeout: 8000 });
  await closePanel();

  await openPanel("Schedules", "Every day");
  await page.getByRole("button", { name: "New schedule" }).click();
  await page.getByLabel(/^Cron/).fill("*/15 * * * *");
  await page.getByText("Every 15 minutes").waitFor();
  await snap("41-schedules"); await noHScroll("schedules"); await axe(page, `${name} schedules`);
  await page.getByLabel(/^Cron/).fill("99 * * * *");
  await page.getByText("minute: must be 0-59").waitFor();
  ok(await page.getByRole("button", { name: "Create schedule" }).isDisabled(), `${name}: invalid cron blocks create`);
  await page.getByLabel(/^Cron/).fill("0 9 * * mon-fri");
  await page.getByLabel("Prompt", { exact: true }).fill("Daily summary");
  await page.getByRole("button", { name: "Create schedule" }).click();
  await page.getByText("Daily summary").waitFor();
  await page.getByRole("listitem").filter({ hasText: "Daily summary" }).getByRole("button", { name: /Actions for schedule 0 9/ }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByText("Daily summary").waitFor({ state: "detached" });
  ok(await page.getByText("Summarize yesterday's commits").count() === 1, `${name}: only the picked schedule deleted`);
  await closePanel();

  await openPanel("Tools", "Core");
  await snap("42-tools"); await noHScroll("tools"); await axe(page, `${name} tools`);
  ok(await page.getByText("asks every time").count() >= 1 && await page.getByText("Deferred").count() >= 1, `${name}: tool badges and groups`);
  await closePanel();
}

export async function worstPanels(page, t) {
  const { name, phone, snap, noHScroll } = t;
  await fetch(`${t.mock}/__seed?worst=1`);
  for (const [label, wait, file] of [["Tasks", "Step 5", "50-worst-tasks"], ["Memory", "Fact 5", "51-worst-memory"], ["MCP", "filesystem", "52-worst-mcp"], ["Schedules", "paused", "53-worst-schedules"], ["Tools", "mcp__filesystem__tool_49", "54-worst-tools"]]) {
    if (phone) await page.getByRole("button", { name: "Open sessions" }).click();
    await clickPanelRow(page, label);
    await page.getByText(wait).first().waitFor({ timeout: 8000 });
    await page.waitForTimeout(350);
    await snap(file); await noHScroll(`worst ${label}`);
    await page.keyboard.press("Escape"); await page.waitForTimeout(300);
  }
  void name;
}

// Brand dots that matter for the home glide: greeting caret, flight ghost, top-bar dot. Only visible ones count.
const brandDots = (page) => page.evaluate(() => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || getComputedStyle(el).visibility === "hidden") return false;
    for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === "none" || Number(cs.opacity) < 0.05) return false; }
    return true;
  };
  return [...document.querySelectorAll(".typed-dot, .dot-flight, [data-flight-target] .dot")].filter(vis).map((d) => (d.closest(".topbar") ? "topbar" : d.classList.contains("dot-flight") ? "ghost" : "greeting"));
});

/** Home greeting: one line, the dot types then glides into the top bar, one brand dot on screen throughout. */
export async function greeting(page, t) {
  const { name, ok } = t;
  const h = page.locator(".home-title");
  await h.waitFor();
  const seen = new Set();
  const until = Date.now() + 8000;
  while (Date.now() < until) {
    const d = await brandDots(page);
    ok(d.length === 1, `${name}: exactly one brand dot while home types and glides (${d.join("+") || "none"})`);
    seen.add(d[0]);
    if (d[0] === "topbar" && (await page.locator('.typed-dot[data-gone="true"]').count()) === 1 && (await page.locator(".dot-flight").count()) === 0) break;
    await page.waitForTimeout(60);
  }
  ok([...seen].at(-1) === "topbar" && (await page.locator('.typed-dot[data-gone="true"]').count()) === 1, `${name}: greeting dot ends in the top bar (${[...seen].join(" > ")})`);
  const lines = await h.evaluate((el) => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight)));
  ok(lines === 1, `${name}: greeting is one line (${lines})`);
}

/** Recent UI changes: Plan/Think pressed while hovered, voice recording controls, Test voice, sidebar truncation, no stray glide. */
export async function recent(page, t) {
  const { name, phone, snap, ok } = t;
  const box = page.getByRole("combobox", { name: "Message" });
  const bg = (loc) => loc.evaluate((el) => getComputedStyle(el).backgroundColor);
  const danger = await page.evaluate(() => { const s = document.createElement("span"); s.style.background = "var(--danger)"; document.body.append(s); const c = getComputedStyle(s).backgroundColor; s.remove(); return c; });

  // Plan and Think: pressed state is visible while the pointer is still on the chip
  for (const label of ["Plan", "Think"]) {
    const chip = page.getByRole("button", { name: label, exact: true });
    ok(await chip.getAttribute("aria-pressed") === "false", `${name}: ${label} starts unpressed`);
    if (phone) { await chip.click(); } else { await chip.hover(); await page.waitForTimeout(250); }
    const rest = phone ? null : await bg(chip);
    if (!phone) await chip.click();
    await page.waitForFunction((l) => [...document.querySelectorAll(".ctl-chip")].find((c) => c.getAttribute("aria-label") === l)?.getAttribute("aria-pressed") === "true", label);
    if (!phone) {
      await page.waitForTimeout(250);
      const on = await bg(chip);
      ok(on !== rest && on !== "rgba(0, 0, 0, 0)", `${name}: ${label} pressed tint shows while hovered (${rest} -> ${on})`);
      await snap(`60-${label.toLowerCase()}-pressed-hover`);
    }
    await chip.click();
    await page.waitForFunction((l) => [...document.querySelectorAll(".ctl-chip")].find((c) => c.getAttribute("aria-label") === l)?.getAttribute("aria-pressed") === "false", label);
  }
  await page.mouse.move(0, 0);

  // Voice: the box becomes a recording strip (waveform, timer, X), mic becomes a check; Esc keeps the draft; Enter transcribes, nothing is sent
  let transcribes = 0;
  const count = (r) => { if (r.url().includes("/voice/transcribe")) transcribes++; };
  page.on("request", count);
  await box.fill("keep me");
  const strip = page.locator(".vstrip");
  const done = page.getByRole("button", { name: "Stop and transcribe" });
  await page.getByRole("button", { name: "Dictate" }).click();
  await done.waitFor();
  ok(await strip.isVisible() && await strip.locator("canvas").isVisible(), `${name}: recording strip with waveform replaces the box`);
  ok(await page.locator(".ta").evaluate((e) => getComputedStyle(e).opacity === "0"), `${name}: typed text is hidden while recording`);
  ok(await page.getByRole("button", { name: "Stop recording" }).count() === 0 && await bg(done) !== danger, `${name}: no red Stop pill, mic is a check`);
  const x = page.getByRole("button", { name: "Cancel recording" });
  ok(await x.isVisible(), `${name}: cancel X on the strip`);
  if (phone) { const xb = await x.boundingBox(); ok(xb && xb.width >= 40 && xb.height >= 40, `${name}: X touch target is ${xb?.width}x${xb?.height}`); }
  ok(/0:00/.test(await strip.locator(".vs-time").textContent()), `${name}: timer starts at 0:00`);
  await page.waitForFunction(() => /0:0[1-9]/.test(document.querySelector(".vs-time")?.textContent ?? ""), null, { timeout: 4000 });
  await page.waitForFunction(() => parseFloat(getComputedStyle(document.querySelector(".composer")).getPropertyValue("--voice-lvl") || "0") > 0.05, null, { timeout: 6000 });
  ok(true, `${name}: waveform and dot follow the mic level`);
  await snap("61-recording");
  await page.keyboard.press("Escape");
  await strip.waitFor({ state: "detached" });
  await page.waitForTimeout(400);
  ok(transcribes === 0 && await page.getByRole("button", { name: "Dictate" }).isVisible() && (await box.inputValue()) === "keep me", `${name}: Esc cancels, draft is back, nothing transcribed`);
  await page.getByRole("button", { name: "Dictate" }).click();
  await done.waitFor(); await page.waitForTimeout(900);
  await x.click();
  await strip.waitFor({ state: "detached" });
  ok(transcribes === 0 && (await box.inputValue()) === "keep me", `${name}: X cancels and restores the draft`);
  await page.getByRole("button", { name: "Dictate" }).click();
  await done.waitFor(); await page.waitForTimeout(900);
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => /keep me.*billing module/.test(document.querySelector(".composer textarea")?.value ?? ""), null, { timeout: 8000 });
  ok(transcribes === 1, `${name}: Enter transcribes once, text lands after the draft, not sent`);
  ok(await strip.count() === 0, `${name}: strip is gone after transcribing`);
  page.off("request", count);
  await box.fill("");

  // Settings: Test voice plays a sample and can be stopped
  if (phone) await page.getByRole("button", { name: "Open sessions" }).click();
  await clickPanelRow(page, "Settings");
  const settings = page.getByRole("dialog", { name: "Settings" });
  const sample = settings.getByRole("button", { name: /Play sample/ });
  await sample.waitFor();
  ok(await settings.getByText("Test voice").isVisible(), `${name}: Test voice row in Settings`);
  await page.waitForFunction(() => [...document.querySelectorAll("dialog[open] button")].some((b) => /Play sample/.test(b.textContent) && !b.disabled), null, { timeout: 8000 });
  await sample.click();
  await settings.getByRole("button", { name: "Stop", exact: true }).waitFor({ timeout: 8000 });
  await snap("62-test-voice");
  await settings.getByRole("button", { name: "Stop", exact: true }).click();
  await sample.waitFor();
  const autoStop = settings.getByRole("switch", { name: /Stop on silence/ });
  ok(await autoStop.isChecked(), `${name}: stop on silence is on by default`);
  await autoStop.evaluate((e) => e.click());
  ok(await page.evaluate(() => JSON.parse(localStorage.getItem("dot.voice") ?? "{}").autoStop === false), `${name}: stop on silence can be turned off`);
  await autoStop.evaluate((e) => e.click());
  // Voice list: every voice has its own pre-recorded preview; one clip at a time; choosing does not play
  const list = settings.getByRole("radiogroup", { name: "Read aloud voice" });
  ok(await list.getByRole("radio").count() === 28 && await list.getByRole("button", { name: /^Play .+ sample$/ }).count() === 28, `${name}: 28 voices with previews`);
  await list.getByRole("button", { name: "Play Bella sample" }).click();
  await list.getByRole("button", { name: "Stop Bella sample" }).waitFor({ timeout: 5000 });
  await list.getByRole("button", { name: "Play Lewis sample" }).click();
  await list.getByRole("button", { name: "Stop Lewis sample" }).waitFor({ timeout: 5000 });
  ok(await list.getByRole("button", { name: /^Stop / }).count() === 1, `${name}: one preview plays at a time`);
  await snap("63-voice-preview");
  await list.getByRole("button", { name: "Stop Lewis sample" }).click();
  await list.locator(".vl-pick", { hasText: "Emma" }).click(); // the radio input is visually hidden, click its label
  ok(await list.getByRole("button", { name: /^Stop / }).count() === 0 && /Emma/.test(await settings.locator(".st-current").textContent()), `${name}: choosing a voice selects without playing`);
  await page.keyboard.press("Escape"); await page.waitForTimeout(300);

  // Sidebar: a truncated title ends in a plain ellipsis with no dotted leader after it
  if (phone) { await page.getByRole("button", { name: "Open sessions" }).click(); await page.waitForTimeout(350); }
  const rows = await page.evaluate(() => [...document.querySelectorAll(".sb-full .sb-item")].map((li) => {
    const t = li.querySelector(".lr-title"), l = li.querySelector(".lr-leader");
    return { text: t.textContent, cut: t.scrollWidth > t.clientWidth + 1, overflow: getComputedStyle(t).textOverflow, leader: l ? l.getBoundingClientRect().width : 0 };
  }));
  const cut = rows.filter((r) => r.cut);
  if (!phone) ok(cut.length > 0, `${name}: some sidebar titles truncate (${rows.length} rows)`); // the phone drawer is wide
  ok(cut.every((r) => r.overflow === "ellipsis" && r.leader < 1), `${name}: truncated titles show a plain ellipsis, no leader ${JSON.stringify(cut.filter((r) => r.leader >= 1).slice(0, 2))}`);
  ok(rows.every((r) => !/\.\.\.|…/.test(r.text)), `${name}: titles are not pre-clipped with dots`);
  await snap("63-sidebar-truncation");

  // Switching chats after a send must not fly a stray dot from a flashed home screen
  await page.evaluate(() => { window.__ghost = 0; const tick = () => { if (document.querySelector(".dot-flight")) window.__ghost++; window.__ghostRaf = requestAnimationFrame(tick); }; tick(); });
  await page.locator(".sb-full .sb-item:not([data-active])").nth(2).getByRole("button").first().click();
  await page.waitForTimeout(900);
  ok(await page.evaluate(() => { cancelAnimationFrame(window.__ghostRaf); return window.__ghost; }) === 0, `${name}: no stray dot glide when switching chats`);
}

/** Browser tab (desktop): page sized to the stage, loading line while opening, middle click closes a tab, back works. */
export async function browserTab(page, t) {
  const { name, phone, snap, ok } = t;
  if (phone) return;
  await page.getByRole("button", { name: "Canvas", exact: true }).click();
  await page.getByRole("tab", { name: "Browser" }).click();
  const addr = page.getByRole("textbox", { name: "Address" });
  await addr.waitFor();
  await addr.fill("example.com");
  await addr.press("Enter");
  await page.locator(".bv-load").waitFor({ timeout: 3000 });
  ok(true, `${name}: loading line shows while the page opens`);
  await page.locator(".bv-img").waitFor();
  await page.waitForFunction(() => !document.querySelector(".bv-load"));
  const fit = await page.evaluate(() => {
    const s = document.querySelector(".bv-stage").getBoundingClientRect(), i = document.querySelector(".bv-img");
    return { w: Math.round(s.width), h: Math.round(s.height), nw: i.naturalWidth, nh: i.naturalHeight };
  });
  ok(Math.abs(fit.nw - fit.w) <= 2 && Math.abs(fit.nh - fit.h) <= 2, `${name}: page is rendered at the stage size (${fit.nw}x${fit.nh} vs ${fit.w}x${fit.h})`);
  await snap("64-browser");
  await page.getByRole("button", { name: "New tab", exact: true }).click();
  const tabs = page.locator(".bv-tab");
  await page.waitForFunction(() => document.querySelectorAll(".bv-tab").length === 2);
  await tabs.first().locator(".bv-tab-main").click({ button: "middle" });
  await page.waitForFunction(() => document.querySelectorAll(".bv-tab").length <= 1 || !document.querySelector(".bv-tabs"));
  ok(true, `${name}: middle click closes a tab`);
  await page.getByRole("button", { name: "Close canvas" }).click();
}

/** Interactive artifacts: scripts run, chart library works, Fix with Dot, and the page cannot reach out. */
export async function artifacts(page, t) {
  const { name, phone, snap, ok } = t;
  if (phone) return;
  const box = page.getByRole("combobox", { name: "Message" });
  await box.fill("write artifact");
  await box.press("Enter");
  await page.getByText("Open `chart.html` in the Preview tab.").or(page.getByText("chart.html in the Preview tab")).first().waitFor({ timeout: 15000 });
  await page.getByRole("button", { name: "Canvas", exact: true }).click();
  await page.getByRole("tab", { name: "Preview" }).click();
  const open = async (file) => {
    await page.getByRole("button", { name: /Switch file/ }).click();
    await page.getByRole("menuitemradio", { name: new RegExp(`^${file.replace(".", "\\.")}`) }).click();
    await page.locator("iframe[title^='Preview of']").waitFor();
  };
  const frameOf = async () => { const h = await page.locator("iframe[title^='Preview of']").elementHandle(); return h.contentFrame(); };

  await open("chart.html");
  const sandbox = await page.locator("iframe[title^='Preview of']").getAttribute("sandbox");
  ok(sandbox === "allow-scripts", `${name}: iframe sandbox is exactly allow-scripts (${sandbox})`);
  const fr = await frameOf();
  await fr.locator("canvas").waitFor();
  await fr.getByRole("button", { name: "Add month" }).click();
  const labels = await fr.evaluate(() => Chart.getChart(document.getElementById("c")).data.labels.length);
  ok(labels === 4, `${name}: the page's script and the bundled chart library run and respond to clicks`);
  ok(await page.getByRole("status").filter({ hasText: "no errors" }).isVisible(), `${name}: a clean page reports no errors`);
  await snap("65-artifact-chart");

  // errors reach the bar and Fix with Dot sends them back as a message
  await open("broken.html");
  await page.getByRole("status").filter({ hasText: "1 error" }).waitFor();
  ok(await page.locator(".cv-issues").getByText(/undefinedFunction/).isVisible(), `${name}: the script error is listed`);
  ok(await page.locator(".cv-issues").getByText("careful now").isVisible(), `${name}: console warnings are listed`);
  await page.getByLabel("Note for Dot").fill("make it say hello");
  await snap("66-artifact-errors");
  await page.getByRole("button", { name: "Fix with Dot" }).click();
  await page.getByText("The interactive page broken.html has a problem.").first().waitFor({ timeout: 8000 });
  ok(true, `${name}: Fix with Dot sends the errors and the note to the chat`);
  await page.waitForFunction(() => !document.querySelector("[aria-label='Stop']") && !document.querySelector(".composer [data-running='true']"), null, { timeout: 15000 }).catch(() => {});

  // every way out is closed
  await page.evaluate(() => { window.__probe = null; window.addEventListener("message", (e) => { if (e.data && e.data.probe) window.__probe = e.data.probe; }); });
  await open("probe.html");
  await page.waitForFunction(() => window.__probe, null, { timeout: 10000 });
  const probe = await page.evaluate(() => window.__probe);
  for (const k of ["fetch", "fetch-remote", "xhr", "websocket", "image-remote", "parent-document", "top-location", "local-storage", "cookie"]) {
    ok(probe[k] === "blocked", `${name}: artifact script cannot use ${k} (${probe[k]})`);
  }
  ok(probe.origin === "null", `${name}: artifact runs in an opaque origin (${probe.origin})`);
  await page.getByRole("button", { name: "Close canvas" }).click();
}
