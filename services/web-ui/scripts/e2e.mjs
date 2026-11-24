// E2E + screenshots: spawns the mock backend and `next start`, drives headless Chromium.
// Usage: node scripts/e2e.mjs [--no-shots] [--worst]   (run `npm run build` first)
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";
import { axe, axeFindings, features, worstPanels } from "./e2e-features.mjs";

const WEB = 3199, MOCK = 8799;
const shots = !process.argv.includes("--no-shots");
const worst = process.argv.includes("--worst");
const out = new URL("../shots/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });

function chromePath() {
  const root = join(homedir(), ".cache/ms-playwright");
  for (const d of readdirSync(root).filter((x) => x.startsWith("chromium-"))) {
    const p = join(root, d, "chrome-linux64/chrome");
    if (existsSync(p)) return p;
  }
  throw new Error("no cached chromium");
}

const procs = [];
const run = (cmd, args, env) => { const p = spawn(cmd, args, { env: { ...process.env, ...env }, stdio: "ignore" }); procs.push(p); return p; };
const until = async (url, ms = 20000) => { const t = Date.now(); while (Date.now() - t < ms) { try { if ((await fetch(url)).status < 500) return; } catch { /* retry */ } await new Promise((r) => setTimeout(r, 200)); } throw new Error(`timeout ${url}`); };

let passed = 0;
const ok = (cond, msg) => { if (!cond) throw new Error(`FAIL: ${msg}`); passed++; };

async function flow(browser, name, vp, scheme) {
  const ctx = await browser.newContext({ viewport: vp, colorScheme: scheme, deviceScaleFactor: 1, hasTouch: vp.width < 600, isMobile: vp.width < 600 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && errors.push(m.text()));
  const snap = async (n) => { if (shots) await page.screenshot({ path: `${out}${name}-${n}.png` }); };
  const phone = vp.width < 600;
  const noHScroll = async (label) => ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${name}: no horizontal scroll (${label})`);
  const openRail = async () => { if (phone) await page.getByRole("button", { name: "Open sessions" }).click(); };
  const send = async (text) => { const box = page.getByRole("combobox", { name: "Message" }); await box.fill(text); await box.press("Enter"); };
  const idle = () => page.waitForFunction(() => document.querySelector(".topbar-label")?.textContent === "Idle", null, { timeout: 15000 });

  await fetch(`http://127.0.0.1:${MOCK}/__reset`);
  await page.goto(`http://127.0.0.1:${WEB}/`);
  await page.getByText("No session open").waitFor();
  await snap("01-no-session"); await noHScroll("empty");
  await page.getByRole("button", { name: "New session" }).first().click();
  await page.getByText("Ready when you are").waitFor();
  await snap("02-empty-session");

  await send("summarize the repo");
  await page.getByText("Waiting for the model").or(page.locator(".thinking")).first().waitFor();
  await page.waitForSelector('.dot[data-state="thinking"]', { state: "attached" });
  ok(await page.locator('.topbar-label').textContent() === "Thinking", `${name}: dot thinking`);
  await snap("03-thinking");
  await idle();
  await page.locator(".tool-row").first().click();
  await snap("04-tool-expanded"); await noHScroll("tool");

  await send("show me code");
  await page.waitForSelector(".code-body .shiki, .code-body pre.shiki", { timeout: 10000 });
  await idle();
  ok(await page.locator(".code-body .shiki").count() > 0, `${name}: shiki highlighted`);
  await snap("05-markdown-code"); await noHScroll("markdown");

  await send("edit the app");
  await page.getByRole("alertdialog").waitFor();
  ok(await page.locator('.dot[data-state="waiting"]').count() > 0, `${name}: dot waiting`);
  await snap("06-approval");
  await page.keyboard.press("a"); // inside the arming delay: ignored
  ok(await page.getByRole("alertdialog").count() === 1, `${name}: early key ignored`);
  await page.waitForTimeout(900);
  await noHScroll("approval");
  await page.keyboard.press("a");
  await page.getByRole("alertdialog").waitFor({ state: "detached" });
  await idle();
  await send("bash something");
  await page.getByRole("alertdialog").waitFor(); await page.waitForTimeout(900);
  await page.keyboard.press("r");
  await idle();
  ok(await page.getByText("left the file alone").count() > 0, `${name}: reject flow`);

  await page.getByRole("combobox", { name: "Message" }).fill("/");
  await page.getByRole("listbox", { name: "Commands" }).waitFor();
  ok(await page.getByRole("option", { name: /review/ }).count() === 1, `${name}: skills in slash menu`);
  await snap("07-slash");
  await page.getByRole("combobox", { name: "Message" }).fill("");

  await page.getByRole("button", { name: /Permission mode/ }).click();
  await page.waitForTimeout(250);
  await snap("08-mode-menu");
  await page.getByRole("option", { name: /Bypass/ }).click();
  await page.getByRole("dialog", { name: /bypass/i }).waitFor();
  await page.waitForTimeout(350);
  await snap("09-bypass-confirm");
  await page.getByRole("button", { name: /Keep/ }).click();

  const panel = async (label, file, wait) => { await openRail(); await page.getByRole("button", { name: label }).click(); await page.getByText(wait).first().waitFor(); await page.waitForTimeout(350); await snap(file); await page.keyboard.press("Escape"); await page.waitForTimeout(300); };
  await panel("Skills", "10-skills", "Drive the browser worker");
  await panel("Audit log", "11-audit", "classifier");
  await panel("Settings", "13-settings", "Backend message language");
  await page.getByRole("button", { name: "Rewind" }).click();
  await page.getByText("edit the app").first().waitFor(); await page.waitForTimeout(350);
  await snap("14-rewind");
  await page.getByRole("button", { name: /Rewind to before: show me code/ }).click();
  await page.getByRole("button", { name: "Confirm rewind" }).click();
  await page.getByText(/files? restored/).waitFor();
  await snap("15-rewound");
  await page.keyboard.press("Escape");

  await axe(page, `${name} main`);
  const t = { name, phone, snap, noHScroll, send, idle, ok, mock: `http://127.0.0.1:${MOCK}` };
  await features(page, t).catch(async (e) => { await page.screenshot({ path: `${out}fail-features-${name}.png` }); throw e; });

  if (worst && /phone-light|desk-dark|tiny-light/.test(name)) await worstCase(page, name, snap, noHScroll, send, idle, t).catch(async (e) => { await page.screenshot({ path: `${out}fail-${name}.png` }); throw e; });
  ok(errors.length === 0, `${name}: no console errors ${errors.join("|")}`);
  await ctx.close();
}

const openRailIfPhone = async (page) => { const b = page.getByRole("button", { name: "Open sessions" }); if (await b.isVisible()) await b.click(); };

async function worstCase(page, name, snap, noHScroll, send, idle, t) {
  await worstPanels(page, t);
  await openRailIfPhone(page);
  await page.locator(".rail-new").click();
  await page.getByText("Ready when you are").waitFor();
  await page.waitForTimeout(300);
  await send("long output please");
  await page.getByText("cat big.log").first().waitFor({ timeout: 20000 });
  await idle();
  await page.locator(".tool-row").last().click();
  await snap("20-worst-long"); await noHScroll("worst long");
  await page.getByRole("button", { name: /Show all/ }).click();
  await noHScroll("worst long expanded");
  await Promise.all(Array.from({ length: 500 }, (_, i) => fetch(`http://127.0.0.1:${MOCK}/v1/sessions`, { method: "POST", headers: { Authorization: "Bearer mock-token", "Content-Type": "application/json" }, body: JSON.stringify({ title: i % 7 === 0 ? "session " + "very-long-unbroken-title-".repeat(8) + i : `Session ${i} Привет Oʻzbek 🙂` }) })));
  const t0 = Date.now();
  await page.reload();
  await page.locator(".session").first().waitFor({ state: "attached" });
  ok(Date.now() - t0 < 4000, `${name}: 500 sessions render fast (${Date.now() - t0}ms)`);
  await page.getByRole("button", { name: "Open sessions" }).click().catch(() => {});
  await page.waitForTimeout(350);
  await snap("22-worst-500-sessions"); await noHScroll("500 sessions");
  await page.keyboard.press("Escape");
  await page.locator(".scrim").click().catch(() => {});
  await send("x".repeat(3000) + " نص عربي 🙂 Привет Oʻzbek");
  await page.waitForTimeout(500);
  await idle(); await snap("21-worst-user-text"); await noHScroll("worst user text");
}

(async () => {
  run("node", ["scripts/mock-backend.mjs"], { MOCK_PORT: String(MOCK), MOCK_DELAY: "20" });
  run("node", ["node_modules/next/dist/bin/next", "start", "-H", "127.0.0.1", "-p", String(WEB)], { DOT_URL: `http://127.0.0.1:${MOCK}`, DOT_API_TOKEN: "mock-token", });
  await until(`http://127.0.0.1:${MOCK}/health`);
  await until(`http://127.0.0.1:${WEB}/`);
  const browser = await chromium.launch({ executablePath: chromePath(), args: ["--no-sandbox"] });
  try {
    const combos = [["phone-light", { width: 390, height: 844 }, "light"], ["phone-dark", { width: 390, height: 844 }, "dark"], ["desk-light", { width: 1440, height: 900 }, "light"], ["desk-dark", { width: 1440, height: 900 }, "dark"], ["tiny-light", { width: 320, height: 640 }, "light"], ["tiny-dark", { width: 320, height: 640 }, "dark"]];
    for (const [n, vp, s] of combos) { await flow(browser, n, vp, s); console.log(`ok ${n}`); }
    if (axeFindings.length) throw new Error(`axe serious/critical:\n${[...new Set(axeFindings)].join("\n")}`);
    console.log(`e2e passed: ${passed} assertions, axe clean`);
  } finally {
    await browser.close();
    procs.forEach((p) => p.kill());
  }
})().catch((e) => { console.error(e); procs.forEach((p) => p.kill()); process.exit(1); });
