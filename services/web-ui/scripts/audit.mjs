// Audit screenshots: node scripts/audit.mjs <webPort> <outDir>. Every step is guarded so one failure never aborts the run.
import { mkdirSync } from "node:fs";
import { launch, newPage, VIEWPORTS } from "./pw.mjs";

const [, , port = "3204", dir = "shots/audit"] = process.argv;
const base = `http://127.0.0.1:${port}`;
mkdirSync(dir, { recursive: true });
const browser = await launch();
const fails = [];
const step = async (name, fn) => { try { await fn(); } catch (e) { fails.push(`${name}: ${String(e).split("\n")[0]}`); } };

async function open(vp, scheme, palette = "sage") {
  const page = await newPage(browser, { viewport: vp, scheme });
  await page.addInitScript(([p]) => { try { const k = "dot.settings"; const o = JSON.parse(localStorage.getItem(k) ?? "{}"); o.palette = p; localStorage.setItem(k, JSON.stringify(o)); } catch {} }, [palette]);
  await page.goto(base);
  await page.waitForTimeout(1200);
  return page;
}
const send = async (page, text) => { const box = page.getByRole("combobox", { name: "Message" }); await box.fill(text); await box.press("Enter"); };
const idle = (page) => page.waitForFunction(() => document.querySelector(".topbar-label")?.textContent === "Idle" || !document.querySelector(".topbar-label"), null, { timeout: 15000 }).catch(() => {});
const openDrawer = async (page, phone) => { if (phone) await page.getByRole("button", { name: "Open sessions" }).click().catch(() => {}); await page.waitForTimeout(300); };

// 1. full flow at desktop, both schemes
for (const scheme of ["light", "dark"]) {
  const page = await open(VIEWPORTS.desktop, scheme);
  const S = (n) => page.screenshot({ path: `${dir}/d-${scheme}-${n}.png` });
  await step("home", () => S("01-home"));
  await step("think", async () => { await send(page, "summarize the repo"); await page.waitForTimeout(500); await S("02-thinking"); await idle(page); await page.waitForTimeout(400); await S("03-answer"); });
  await step("tool", async () => { await page.locator(".activity-head").first().click(); await page.locator(".tool-row").first().click(); await page.waitForTimeout(300); await S("04-tool-open"); });
  await step("widgets", async () => { await send(page, "show me widgets"); await idle(page); await page.waitForTimeout(600); await S("05-widgets"); });
  await step("code", async () => { await send(page, "show me code"); await page.waitForSelector(".code-body .shiki", { timeout: 10000 }); await idle(page); await page.waitForTimeout(400); await S("06-code"); });
  await step("approval", async () => { await send(page, "edit the app"); await page.getByRole("alertdialog").waitFor(); await page.waitForTimeout(1000); await S("07-approval"); await page.keyboard.press("a"); await idle(page); });
  await step("plan", async () => { await send(page, "plan the work"); await page.waitForTimeout(2500); await S("08-plan"); await idle(page); });
  await step("slash", async () => { const b = page.getByRole("combobox", { name: "Message" }); await b.fill("/"); await page.waitForTimeout(300); await S("09-slash"); await b.fill(""); });
  await step("mode", async () => { await page.getByRole("button", { name: /Permission mode/ }).click(); await page.waitForTimeout(300); await S("10-mode-menu"); await page.keyboard.press("Escape"); });
  await step("plus", async () => { await page.getByRole("button", { name: "Add and tools" }).click(); await page.waitForTimeout(300); await S("11-plus-menu"); await page.keyboard.press("Escape"); });
  await step("context", async () => { await page.getByRole("button", { name: /Context/ }).first().click(); await page.waitForTimeout(300); await S("12-context"); await page.keyboard.press("Escape"); });
  await step("canvas", async () => { await page.getByRole("button", { name: "Canvas", exact: true }).click(); await page.waitForTimeout(500); await S("13-canvas-preview");
    for (const t of ["Files", "Browser"]) { await page.getByRole("tab", { name: t }).click().catch(() => {}); await page.waitForTimeout(400); await S(`14-canvas-${t.toLowerCase()}`); }
    await page.getByRole("button", { name: "Canvas", exact: true }).click(); await page.waitForTimeout(300); });
  await step("rail", async () => { await page.getByRole("button", { name: "Collapse sidebar" }).click(); await page.waitForTimeout(500); await S("15-rail"); await page.getByRole("button", { name: /Expand sidebar|Open sidebar/ }).first().click().catch(() => {}); await page.waitForTimeout(400); });
  await step("palette", async () => { await page.keyboard.press("Control+k"); await page.waitForTimeout(400); await S("16-cmdk"); await page.keyboard.press("Escape"); });
  await step("account", async () => { await page.locator(".sb-account").first().click(); await page.waitForTimeout(300); await S("17-account-menu"); await page.keyboard.press("Escape"); });
  await step("sessmenu", async () => { await page.locator(".sb-session").nth(6).hover(); await page.locator(".sb-session [aria-label*='ore'], .sb-more").first().click().catch(() => {}); await page.waitForTimeout(300); await S("18-session-menu"); await page.keyboard.press("Escape"); });
  let i = 20;
  for (const label of ["Tasks", "Schedules", "Memory", "Skills"]) await step(label, async () => { await page.locator(".sb-navrow", { hasText: label }).click(); await page.waitForTimeout(600); await S(`${i++}-panel-${label.toLowerCase()}`); await page.keyboard.press("Escape"); await page.waitForTimeout(300); });
  for (const label of ["MCP", "Tools", "Audit log", "Settings"]) await step(label, async () => { await page.locator(".sb-account").first().click(); await page.getByRole("menuitem", { name: label }).click(); await page.waitForTimeout(700); await S(`${i++}-panel-${label.replace(" ", "").toLowerCase()}`); await page.keyboard.press("Escape"); await page.waitForTimeout(300); });
  await step("rewind", async () => { await page.getByRole("button", { name: "Rewind", exact: true }).click(); await page.waitForTimeout(600); await S("30-rewind"); await page.keyboard.press("Escape"); });
  await step("kit", async () => { await page.goto(`${base}/kit?theme=${scheme}`); await page.waitForTimeout(800); await page.screenshot({ path: `${dir}/d-${scheme}-31-kit.png`, fullPage: true }); });
  if (page.errors.length) fails.push(`${scheme} console: ${page.errors.slice(0, 3).join("|")}`);
  await page.context().close();
}

// 2. responsive
for (const vn of ["tablet", "phone", "tiny"]) for (const scheme of ["light", "dark"]) {
  const vp = VIEWPORTS[vn]; const phone = vp.width < 700;
  const page = await open(vp, scheme);
  const S = (n) => page.screenshot({ path: `${dir}/${vn}-${scheme}-${n}.png` });
  await step(vn + "home", () => S("1-home"));
  await step(vn + "widgets", async () => { await send(page, "show me widgets"); await idle(page); await page.waitForTimeout(600); await S("2-widgets"); });
  await step(vn + "code", async () => { await send(page, "show me code"); await idle(page); await page.waitForTimeout(500); await S("3-code"); });
  await step(vn + "approval", async () => { await send(page, "edit the app"); await page.getByRole("alertdialog").waitFor(); await page.waitForTimeout(1000); await S("4-approval"); await page.keyboard.press("a"); await idle(page); });
  await step(vn + "drawer", async () => { await openDrawer(page, phone); await S("5-sidebar"); });
  await step(vn + "settings", async () => { await page.locator(".sb-account").first().click(); await page.getByRole("menuitem", { name: "Settings" }).click(); await page.waitForTimeout(700); await S("6-settings"); });
  await page.context().close();
}

// 3. palettes on three screens
for (const pal of ["sage", "clay", "ink", "plum", "sand", "mono"]) for (const scheme of ["light", "dark"]) {
  const page = await open(VIEWPORTS.desktop, scheme, pal);
  const S = (n) => page.screenshot({ path: `${dir}/pal-${pal}-${scheme}-${n}.png` });
  await step(pal + "home", () => S("1-home"));
  await step(pal + "widgets", async () => { await send(page, "show me widgets"); await idle(page); await page.waitForTimeout(600); await S("2-widgets"); });
  await step(pal + "approval", async () => { await send(page, "edit the app"); await page.getByRole("alertdialog").waitFor(); await page.waitForTimeout(1000); await S("3-approval"); });
  await page.context().close();
}
await browser.close();
console.log(fails.length ? "FAILS:\n" + fails.join("\n") : "all ok");
