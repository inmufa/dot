// Greeting dot probe: frame sheets of the home dot glide, a per-frame count of visible brand dots, one-line greeting check.
// Usage: node scripts/greeting-dot.mjs <base url> <out dir> [--send=early|late] [--switch]
//   --send sends ONE message from home (early: while typing, late: after the glide); costs a model turn on a live site.
//   --switch (mock only, sends): send in a chat, open New chat, then pick another chat; no glide may play.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { frameSheet, launch } from "./pw.mjs";

const [base, out] = process.argv.slice(2);
const sendArg = process.argv.find((a) => a.startsWith("--send"));
const doSend = Boolean(sendArg);
const early = sendArg === "--send=early";
const doSwitch = process.argv.includes("--switch");
const skipLoad = process.argv.includes("--no-load");
if (!base || !out) throw new Error("usage: greeting-dot.mjs <base url> <out dir> [--send]");
mkdirSync(out, { recursive: true });
const GREETINGS = [...readFileSync(new URL("../src/lib/greetings.ts", import.meta.url), "utf8").matchAll(/^\s+"(.+)",$/gm)].map((m) => m[1].replace(/\\"/g, '"'));

// Samples every animation frame: brand dots (greeting caret, glide ghost, top-bar dot) that are actually visible.
const SAMPLER = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.top > innerHeight) return null;
    if (getComputedStyle(el).visibility === "hidden") return null;
    for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === "none" || Number(cs.opacity) < 0.05) return null; }
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
  };
  const log = (window.__dots = []);
  const t0 = performance.now();
  const tick = () => {
    const seen = [];
    for (const [kind, sel] of [["greeting", ".typed-dot"], ["ghost", ".dot-flight"], ["topbar", "[data-flight-target] .dot"]]) {
      for (const el of document.querySelectorAll(sel)) { const p = vis(el); if (p) seen.push({ kind, ...p }); }
    }
    log.push({ t: Math.round(performance.now() - t0), seen });
    window.__dotRaf = requestAnimationFrame(tick);
  };
  tick();
};

const summary = (log) => {
  const bad = log.filter((f) => f.seen.length !== 1);
  const kinds = [];
  for (const f of log) { const k = f.seen.map((s) => s.kind).join("+") || "none"; if (kinds.at(-1)?.k !== k) kinds.push({ k, t: f.t }); }
  return { frames: log.length, badFrames: bad.length, firstBad: bad.slice(0, 5), sequence: kinds, last: log.at(-1)?.seen };
};

// Each greeting, rendered in the real h1, must fit on one line.
const oneLine = (page) => page.evaluate((GREETINGS) => {
  const h = document.querySelector(".home-title");
  const span = h.querySelector("span[aria-hidden]:not(.dot)");
  const keep = span.textContent;
  const lh = parseFloat(getComputedStyle(h).lineHeight);
  const res = [];
  for (const g of GREETINGS) {
    span.textContent = g;
    const r = h.getBoundingClientRect();
    const right = h.parentElement.getBoundingClientRect().right;
    res.push({ g, lines: Math.round(r.height / lh), overflow: Math.round(h.scrollWidth - h.clientWidth), pastEdge: Math.round(r.right - Math.min(right, innerWidth)) });
  }
  span.textContent = keep;
  return { lineHeight: lh, fontSize: getComputedStyle(h).fontSize, bad: res.filter((x) => x.lines !== 1 || x.overflow > 0 || x.pastEdge > 0), checked: res.length, current: keep };
}, GREETINGS);

const browser = await launch();
const report = {};
try {
  for (const [label, vp] of skipLoad ? [] : [["1440", { width: 1440, height: 900 }], ["1024", { width: 1024, height: 768 }], ["390", { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 1, hasTouch: vp.width < 600, isMobile: vp.width < 600 });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.addInitScript(SAMPLER);
    const r = { errors };
    // load: typing, then the dot glides to the top bar on its own
    await page.goto(base);
    await page.locator(".topbar").waitFor();
    await page.waitForTimeout(1500);
    if (vp.width < 600) await page.getByRole("button", { name: "Open sessions" }).click();
    await page.evaluate(() => { cancelAnimationFrame(window.__dotRaf); });
    r.load = await frameSheet(page, out, `load-${label}`, async () => {
      await page.evaluate(SAMPLER);
      await page.getByRole("button", { name: "New chat" }).first().click();
      await page.locator(".home-title").waitFor();
      await page.waitForFunction(() => document.querySelector(".typed-dot")?.dataset.gone === "true", null, { timeout: 15000 });
      await page.waitForTimeout(900);
    }, { every: 60, cols: 6, tileW: 320 });
    r.loadDots = summary(await page.evaluate(() => window.__dots));
    r.oneLine = await oneLine(page);
    await page.screenshot({ path: `${out}/home-${label}.png` });
    report[label] = r;
    await ctx.close();
  }
  if (doSend) {
    // one real turn from home: the greeting must hand over to the top-bar dot, never two dots
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.addInitScript(SAMPLER);
    await page.goto(base);
    await page.locator(".topbar").waitFor();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: "New chat" }).first().click();
    await page.locator(".home-title").waitFor();
    if (!early) { await page.waitForFunction(() => document.querySelector(".typed-dot")?.dataset.gone === "true", null, { timeout: 15000 }); await page.waitForTimeout(900); }
    else await page.waitForFunction(() => (document.querySelector(".home-title span[aria-hidden]")?.textContent.length ?? 0) >= 3, null, { timeout: 5000 });
    await page.evaluate(() => { cancelAnimationFrame(window.__dotRaf); });
    await page.evaluate(SAMPLER);
    report.send = await frameSheet(page, out, `send-${early ? "early" : "late"}-1440`, async () => {
      const box = page.getByRole("combobox", { name: "Message" });
      await box.fill("Reply with one word: ok");
      await box.press("Enter");
      await page.locator(".home-title").waitFor({ state: "detached", timeout: 60000 });
      await page.waitForTimeout(900);
    }, { every: 40, cols: 6, tileW: 320 });
    report.sendDots = summary(await page.evaluate(() => window.__dots));
    await page.screenshot({ path: `${out}/after-send-${early ? "early" : "late"}-1440.png` });
    if (doSwitch) {
      await page.locator(".topbar-label").waitFor({ state: "detached", timeout: 180000 });
      await page.getByRole("button", { name: "New chat" }).first().click();
      await page.waitForFunction(() => document.querySelector(".typed-dot")?.dataset.typing === "true", null, { timeout: 5000 });
      await page.evaluate(() => { cancelAnimationFrame(window.__dotRaf); });
      await page.evaluate(SAMPLER);
      // leave home mid-typing for an existing chat: nothing was sent, so no glide
      report.switch = await frameSheet(page, out, "switch-1440", async () => {
        await page.locator(".sb-item").nth(1).getByRole("button").first().click();
        await page.locator(".home-title").waitFor({ state: "detached" });
        await page.waitForTimeout(900);
      }, { every: 40, cols: 6, tileW: 320 });
      report.switchDots = summary(await page.evaluate(() => window.__dots));
    }
    await ctx.close();
  }
} finally {
  await browser.close();
}
writeFileSync(`${out}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, (k, v) => (k === "firstBad" && v.length === 0 ? undefined : v), 2));
