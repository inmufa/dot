// Kit screenshots for every palette x scheme + motion frame sheets. Usage: node scripts/kit-all.mjs [slot] [outDir]
import { mkdirSync } from "node:fs";
import { frameSheet, launch, newPage, VIEWPORTS } from "./pw.mjs";

const slot = Number(process.argv[2] ?? 4), out = process.argv[3] ?? "shots/audit/kit";
mkdirSync(out, { recursive: true });
const base = `http://127.0.0.1:${3200 + slot}`;
const browser = await launch();
const fails = [];
for (const pal of ["sage", "clay", "ink", "plum", "sand", "mono"]) for (const scheme of ["light", "dark"]) {
  const page = await newPage(browser, { viewport: { width: 1200, height: 900 }, scheme });
  await page.goto(`${base}/kit?palette=${pal}&theme=${scheme}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const bad = await page.locator('td[data-pass="false"]').count();
  if (bad) fails.push(`${pal}-${scheme}: ${bad} contrast FAIL`);
  await page.screenshot({ path: `${out}/kit-${pal}-${scheme}.png`, fullPage: true });
  if (page.errors.length) fails.push(`${pal}-${scheme}: ${page.errors.slice(0, 2)}`);
  await page.context().close();
}
const page = await newPage(browser, { viewport: VIEWPORTS.desktop, scheme: "light" });
await page.goto(`${base}/kit?theme=light`, { waitUntil: "networkidle" });
const run = async (name, fn) => { try { const r = await frameSheet(page, out, name, fn, { every: 30, cols: 8, tileW: 240 }); console.log(name, r.frames); } catch (e) { fails.push(`${name}: ${e}`); } };
await run("fs-menu", async () => { await page.getByRole("button", { name: "Actions" }).click(); await page.waitForTimeout(200); await page.keyboard.press("Escape"); });
await run("fs-dialog", async () => { await page.getByRole("button", { name: "Confirm dialog" }).click(); await page.waitForTimeout(350); await page.keyboard.press("Escape"); });
await run("fs-tab", async () => { await page.getByRole("tab", { name: "Preview" }).click(); await page.waitForTimeout(350); });
await run("fs-toast", async () => { await page.getByRole("button", { name: "Toast ok" }).click(); await page.waitForTimeout(500); });
await browser.close();
console.log(fails.length ? "FAILS\n" + fails.join("\n") : "kit ok");
