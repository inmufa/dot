// Phase 6 flows: question, subagent, plan, compaction, taint, context popover, and the new panels.
import { AxeBuilder } from "@axe-core/playwright";

export const axeFindings = [];

export async function axe(page, label) {
  const r = await new AxeBuilder({ page }).analyze();
  for (const v of r.violations.filter((x) => x.impact === "serious" || x.impact === "critical")) {
    axeFindings.push(`${label}: ${v.id} (${v.impact}) ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(" | ")}`);
  }
}

export async function features(page, t) {
  const { name, phone, snap, noHScroll, send, idle, ok } = t;
  const box = page.getByRole("combobox", { name: "Message" });
  const openPanel = async (label, wait) => {
    if (phone) await page.getByRole("button", { name: "Open sessions" }).click();
    await page.locator(".rail-link", { hasText: label }).click();
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
  await page.locator(".sub-row").first().click();
  await page.waitForTimeout(150);
  await snap("32-subagent"); await noHScroll("subagent");
  ok(await page.locator(".sub").count() === 2, `${name}: two subagent lines`);
  ok(await page.locator(".sub-steps .badge").count() >= 4, `${name}: subagent steps listed`);
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
  ok(await page.locator(".plan").count() === 1, `${name}: plan block in transcript`);
  await snap("34-plan-block");

  // compaction divider
  await send("compact please");
  await page.locator(".divider").waitFor();
  await idle();
  ok(/Context compacted\s*12\.1k.*4\.3k/.test((await page.locator(".divider").textContent()) ?? ""), `${name}: compaction divider text`);
  await snap("35-compaction");

  // context popover + compact
  await page.locator(".ctx-btn").click();
  await page.getByText("Prompt layers").waitFor(); await page.waitForTimeout(250);
  await snap("36-context"); await noHScroll("context popover");
  await axe(page, `${name} context`);
  await page.getByRole("button", { name: "Compact now" }).click();
  await page.getByText(/Compacted 7\.2k to 2\.6k/).waitFor();
  await page.keyboard.press("Escape");

  // panels
  await openPanel("Tasks", "Write the failing test");
  ok(await page.locator(".task .badge", { hasText: "blocked" }).count() >= 1, `${name}: blocked task chip`);
  await snap("37-tasks"); await noHScroll("tasks"); await axe(page, `${name} tasks`); await closePanel();

  await openPanel("Memory", "Prefers uv over pip");
  await snap("38-memory"); await noHScroll("memory"); await axe(page, `${name} memory`);
  await page.getByLabel("Search facts").fill("tests");
  await page.getByText("Prefers uv").waitFor({ state: "detached" });
  await page.getByLabel("Search facts").fill("");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByLabel("Name").fill("Temp fact");
  await page.getByLabel("Fact").fill("Delete me");
  await page.getByRole("button", { name: "Save fact" }).click();
  await page.getByText("Temp fact").waitFor();
  await page.getByRole("button", { name: "Delete Temp fact" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByText("Temp fact").waitFor({ state: "detached" });
  ok(true, `${name}: memory add, search, delete with confirm`);
  await closePanel();

  await openPanel("MCP", "project-db");
  await snap("39-mcp"); await noHScroll("mcp"); await axe(page, `${name} mcp`);
  await page.getByRole("button", { name: /Review and trust/ }).click();
  await page.waitForTimeout(150);
  await snap("40-mcp-trust"); await noHScroll("mcp trust");
  await page.getByRole("button", { name: "Trust and start" }).click();
  await page.getByText("connected").nth(1).waitFor({ timeout: 6000 });
  await closePanel();

  await openPanel("Schedules", "Every day");
  await page.getByLabel(/^Cron/).fill("*/15 * * * *");
  await page.getByText("Every 15 minutes").waitFor();
  await snap("41-schedules"); await noHScroll("schedules"); await axe(page, `${name} schedules`);
  await page.getByLabel(/^Cron/).fill("99 * * * *");
  await page.getByText("minute: must be 0-59").waitFor();
  ok(await page.getByRole("button", { name: "Create schedule" }).isDisabled(), `${name}: invalid cron blocks create`);
  await page.getByLabel(/^Cron/).fill("0 9 * * mon-fri");
  await page.getByLabel("Prompt").fill("Daily summary");
  await page.getByRole("button", { name: "Create schedule" }).click();
  await page.getByText("Daily summary").waitFor();
  await page.getByRole("button", { name: /Delete schedule 0 9/ }).first().click();
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
    await page.locator(".rail-link", { hasText: label }).click();
    await page.getByText(wait).first().waitFor({ timeout: 8000 });
    await page.waitForTimeout(350);
    await snap(file); await noHScroll(`worst ${label}`);
    await page.keyboard.press("Escape"); await page.waitForTimeout(300);
  }
  void name;
}
