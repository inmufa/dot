// E2E + screenshots: spawns the mock backend and `next start`, drives headless Chromium.
// Usage: node scripts/e2e.mjs [--no-shots] [--worst]   (run `npm run build` first)
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";
import { axe, axeFindings, artifacts, browserTab, features, greeting, recent, worstPanels } from "./e2e-features.mjs";
import { clickPanelRow } from "./pw-sidebar.mjs";

// E2E_WEB / E2E_MOCK ports reuse a running dev stack instead of spawning next start.
const EXT = Boolean(process.env.E2E_WEB);
const WEB = Number(process.env.E2E_WEB ?? 3199), MOCK = Number(process.env.E2E_MOCK ?? 8799);
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
  const ctx = await browser.newContext({ viewport: vp, colorScheme: scheme, deviceScaleFactor: 1, hasTouch: vp.width < 600, isMobile: vp.width < 600, permissions: ["microphone"] });
  const page = await ctx.newPage();
  try { await flowBody(page, name, vp); } catch (e) { await page.screenshot({ path: `${out}fail-${name}.png` }).catch(() => {}); throw e; } finally { await ctx.close(); }
}

async function flowBody(page, name, vp) {
  const errors = [];
  // artifact pages (files/content) fail on purpose in the artifacts check; their console is not the app's
  const fromArtifact = (m) => /\/v1\/files\/content/.test(m.location().url ?? "");
  page.on("pageerror", (e) => !/undefinedFunction/.test(String(e)) && errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && !fromArtifact(m) && !/Failed to load resource/.test(m.text()) && errors.push(m.text()));
  const snap = async (n) => { if (shots) await page.screenshot({ path: `${out}${name}-${n}.png` }); };
  const phone = vp.width < 600;
  const noHScroll = async (label) => ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${name}: no horizontal scroll (${label})`);
  const openRail = async () => { if (phone) await page.getByRole("button", { name: "Open sessions" }).click(); };
  const send = async (text) => { const box = page.getByRole("combobox", { name: "Message" }); await box.fill(text); await box.press("Enter"); };
  const idle = () => page.waitForFunction(() => !document.querySelector(".topbar-label"), null, { timeout: 15000 });

  await fetch(`http://127.0.0.1:${MOCK}/__reset`);
  await page.goto(`http://127.0.0.1:${WEB}/`);
  await page.locator(".home-title").waitFor();
  await snap("01-no-session"); await noHScroll("empty");
  await openRail();
  await page.getByRole("button", { name: "New chat" }).first().click();
  await page.locator(".home-title").waitFor();
  await greeting(page, { name, ok });
  await snap("02-empty-session");

  await send("summarize the repo");
  await page.getByText("waiting for the model").or(page.locator(".think, .e-answer")).first().waitFor();
  await page.waitForSelector('.dot[data-state="thinking"]', { state: "attached" });
  ok(await page.locator('.topbar-label').textContent() === "thinking", `${name}: dot thinking`);
  await snap("03-thinking");
  await idle();
  await page.locator(".activity-head").first().click();
  await snap("04-steps-open");
  // ChatGPT/Claude-style column: no global rail or time gutter; the thin line stays only between open steps
  const col = await page.evaluate(() => {
    const L = (s) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect() : null; };
    const log = L(".log"), title = L(".topbar-title"), card = L(".composer-card"), main = L(".main");
    const shown = (e, pseudo) => { const c = getComputedStyle(e, pseudo); return c.display !== "none" && parseFloat(c.height) > 0; };
    const entries = [...document.querySelectorAll(".log .entry")];
    const steps = [...document.querySelectorAll(".log .activity .e-step")];
    return {
      left: [log?.left, title?.left, card?.left].map((x) => Math.round(x ?? -1)), width: Math.round(log?.width ?? 0),
      off: Math.round(((log?.left ?? 0) - (main?.left ?? 0)) - ((main?.right ?? 0) - (log?.right ?? 0))),
      stray: entries.filter((e) => !e.classList.contains("e-step") && (getComputedStyle(e, "::before").display !== "none" || getComputedStyle(e.querySelector(".entry-time")).display !== "none")).length,
      stepLines: steps.slice(0, -1).filter((e) => !shown(e, "::before")).length, lastLine: steps.length ? shown(steps[steps.length - 1], "::before") : false, steps: steps.length,
      stepGap: Math.max(0, ...steps.slice(0, -1).map((e, i) => Math.round(steps[i + 1].getBoundingClientRect().top - e.getBoundingClientRect().bottom))),
      bubble: (() => { const u = document.querySelector(".log .u-block"); const b = document.querySelector(".log .e-user .entry-body"); return u && b ? u.getBoundingClientRect().width / b.getBoundingClientRect().width : 0; })(),
    };
  });
  ok(col.stray === 0, `${name}: no rail or time gutter on chat entries (${col.stray})`);
  ok(col.steps === 0 || (col.stepLines === 0 && !col.lastLine && col.stepGap <= 2), `${name}: line continuous between open steps only (${JSON.stringify(col)})`);
  ok(col.width <= 770 && col.bubble <= 0.81, `${name}: column <= 48rem, bubble <= 80% (${col.width}px, ${col.bubble.toFixed(2)})`);
  if (!phone) ok(Math.abs(col.left[0] - col.left[1]) <= 2 && Math.abs(col.left[0] - col.left[2]) <= 2 && Math.abs(col.off) <= 24, `${name}: log, title and composer share one centered column (${col.left}, off ${col.off})`);
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
  await page.getByRole("menuitemradio", { name: /Bypass/ }).click();
  await page.getByRole("dialog", { name: /bypass/i }).waitFor();
  await page.waitForTimeout(350);
  await snap("09-bypass-confirm");
  await page.getByRole("button", { name: /Keep/ }).click();

  const panel = async (label, file, wait) => { await openRail(); await clickPanelRow(page, label); await page.getByText(wait).first().waitFor(); await page.waitForTimeout(350); await snap(file); await page.keyboard.press("Escape"); await page.waitForTimeout(300); };
  await panel("Skills", "10-skills", "Drive the browser worker");
  await panel("Audit log", "11-audit", "classifier");
  await panel("Settings", "13-settings", "Backend messages");
  await page.getByRole("button", { name: "Rewind", exact: true }).click();
  await page.getByText("edit the app").first().waitFor(); await page.waitForTimeout(350);
  await snap("14-rewind");
  await page.getByRole("button", { name: /Rewind to before: show me code/ }).click();
  await page.getByRole("button", { name: "Confirm rewind" }).click();
  await page.getByText(/files? restored/).waitFor();
  await snap("15-rewound");
  await page.keyboard.press("Escape");
  // pointer off the Rewind button so axe never samples a tooltip mid fade-in
  await page.mouse.move(0, 0); await page.waitForTimeout(300);

  await axe(page, `${name} main`);
  const t = { name, phone, snap, noHScroll, send, idle, ok, mock: `http://127.0.0.1:${MOCK}` };
  await features(page, t).catch(async (e) => { await page.screenshot({ path: `${out}fail-features-${name}.png` }); throw e; });
  await browserTab(page, t).catch(async (e) => { await page.screenshot({ path: `${out}fail-browser-${name}.png` }); throw e; });
  await recent(page, t);
  await idle().catch(() => {});
  await artifacts(page, t).catch(async (e) => { await page.screenshot({ path: `${out}fail-artifacts-${name}.png` }); throw e; });

  if (worst && /phone-light|desk-dark|tiny-light/.test(name)) await worstCase(page, name, snap, noHScroll, send, idle, t).catch(async (e) => { await page.screenshot({ path: `${out}fail-${name}.png` }); throw e; });
  ok(errors.length === 0, `${name}: no console errors ${errors.join("|")}`);
}

const openRailIfPhone = async (page) => { const b = page.getByRole("button", { name: "Open sessions" }); if (await b.isVisible()) await b.click(); };

async function worstCase(page, name, snap, noHScroll, send, idle, t) {
  await worstPanels(page, t);
  await openRailIfPhone(page);
  await page.getByRole("button", { name: "New chat" }).first().click();
  await page.getByText("Ready when you are").waitFor();
  await page.waitForTimeout(300);
  await send("long output please");
  await page.getByText("cat big.log").first().waitFor({ timeout: 20000 });
  await idle();
  await page.locator(".activity-head").last().click();
  await page.locator(".tool-row").last().click();
  await snap("20-worst-long"); await noHScroll("worst long");
  await page.getByRole("button", { name: /Show all/ }).click();
  await noHScroll("worst long expanded");
  await Promise.all(Array.from({ length: 500 }, (_, i) => fetch(`http://127.0.0.1:${MOCK}/v1/sessions`, { method: "POST", headers: { Authorization: "Bearer mock-token", "Content-Type": "application/json" }, body: JSON.stringify({ title: i % 7 === 0 ? "session " + "very-long-unbroken-title-".repeat(8) + i : `Session ${i} Привет Oʻzbek 🙂` }) })));
  const t0 = Date.now();
  await page.reload();
  await page.locator(".sb-item, .sb-chat").first().waitFor({ state: "attached" });
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
  if (!EXT) {
    run("node", ["scripts/mock-backend.mjs"], { MOCK_PORT: String(MOCK), MOCK_DELAY: "20" });
    run("node", ["node_modules/next/dist/bin/next", "start", "-H", "127.0.0.1", "-p", String(WEB)], { DOT_URL: `http://127.0.0.1:${MOCK}`, DOT_API_TOKEN: "mock-token", });
  }
  await until(`http://127.0.0.1:${MOCK}/health`);
  await until(`http://127.0.0.1:${WEB}/`);
  const browser = await chromium.launch({ executablePath: chromePath(), args: ["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"] });
  try {
    const combos = [["phone-light", { width: 390, height: 844 }, "light"], ["phone-dark", { width: 390, height: 844 }, "dark"], ["desk-light", { width: 1440, height: 900 }, "light"], ["desk-dark", { width: 1440, height: 900 }, "dark"], ["tiny-light", { width: 320, height: 640 }, "light"], ["tiny-dark", { width: 320, height: 640 }, "dark"]];
    const only = process.env.E2E_ONLY;
    for (const [n, vp, s] of combos) { if (only && !n.includes(only)) continue; await flow(browser, n, vp, s); console.log(`ok ${n}`); }
    if (axeFindings.length) throw new Error(`axe serious/critical:\n${[...new Set(axeFindings)].join("\n")}`);
    console.log(`e2e passed: ${passed} assertions, axe clean`);
  } finally {
    await browser.close();
    procs.forEach((p) => p.kill());
  }
})().catch((e) => { console.error(e); procs.forEach((p) => p.kill()); process.exit(1); });
