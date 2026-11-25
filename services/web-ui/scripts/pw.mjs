// Playwright helpers for visual review: launch, screenshots, and short frame sequences (CDP screencast) tiled into a contact sheet.
// Read the PNGs with the Read tool. Example: see docs/design-brief-v2.md "Reviewing motion".
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";

export function chromePath() {
  const root = join(homedir(), ".cache/ms-playwright");
  for (const d of readdirSync(root).filter((x) => x.startsWith("chromium-"))) {
    const p = join(root, d, "chrome-linux64/chrome");
    if (existsSync(p)) return p;
  }
  throw new Error("no cached chromium");
}
export const launch = () => chromium.launch({ executablePath: chromePath(), args: ["--no-sandbox", "--enable-features=CSSLinearEasing"] });

export const VIEWPORTS = {
  phone: { width: 390, height: 844 }, tablet: { width: 768, height: 1024 }, desktop: { width: 1440, height: 900 }, tiny: { width: 320, height: 640 },
};

export async function newPage(browser, { viewport = VIEWPORTS.desktop, scheme = "dark", reducedMotion = "no-preference" } = {}) {
  const ctx = await browser.newContext({ viewport, colorScheme: scheme, reducedMotion, deviceScaleFactor: 1, hasTouch: viewport.width < 600, isMobile: viewport.width < 600 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && errors.push(m.text()));
  page.errors = errors;
  return page;
}

/**
 * Record frames while `action()` runs. Returns the contact sheet path (frames tiled with timestamps).
 * `every` throttles frames in ms; `scale` shrinks tiles. Needs `uv` (pillow) for the sheet.
 */
export async function frameSheet(page, dir, name, action, { settleMs = 400, every = 40, cols = 6, tileW = 300 } = {}) {
  mkdirSync(dir, { recursive: true });
  const cdp = await page.context().newCDPSession(page);
  const frames = [];
  let t0 = null, last = -1e9;
  cdp.on("Page.screencastFrame", async (f) => {
    const ts = f.metadata.timestamp * 1000;
    t0 ??= ts;
    const t = ts - t0;
    if (t - last >= every) { frames.push({ t, data: f.data }); last = t; }
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 70, everyNthFrame: 1 });
  await action();
  await page.waitForTimeout(settleMs);
  await cdp.send("Page.stopScreencast");
  await cdp.detach();
  const fdir = join(dir, name);
  mkdirSync(fdir, { recursive: true });
  frames.forEach((f, i) => writeFileSync(join(fdir, `${String(i).padStart(3, "0")}_${Math.round(f.t)}ms.jpg`), Buffer.from(f.data, "base64")));
  const out = join(dir, `${name}-sheet.png`);
  const r = spawnSync("uv", ["run", "--with", "pillow", "python", new URL("./montage.py", import.meta.url).pathname, fdir, out, String(cols), String(tileW)], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(r.stderr || "montage failed");
  return { sheet: out, frames: frames.length };
}
