// Screenshots of /kit (every primitive) in light and dark at 1440 and 390, plus open menu/dialog states.
// Usage: dev stack running (scripts/dev-stack.mjs <slot>), then node scripts/kit.mjs [slot] [outDir]
import { mkdirSync } from "node:fs";
import { launch, newPage, VIEWPORTS } from "./pw.mjs";

const slot = Number(process.argv[2] ?? 4);
const out = process.argv[3] ?? "shots/kit";
mkdirSync(out, { recursive: true });
const base = `http://127.0.0.1:${3200 + slot}/kit`;
const browser = await launch();
for (const scheme of ["light", "dark"]) {
  for (const [name, viewport] of [["desktop", VIEWPORTS.desktop], ["phone", VIEWPORTS.phone], ["tiny", VIEWPORTS.tiny]]) {
    const page = await newPage(browser, { viewport, scheme });
    await page.goto(`${base}?theme=${scheme}`, { waitUntil: "networkidle" });
    await page.screenshot({ path: `${out}/${scheme}-${name}.png`, fullPage: true });
    if (name !== "tiny") {
      await page.getByRole("button", { name: "Actions" }).click();
      await page.waitForTimeout(250);
      await page.screenshot({ path: `${out}/${scheme}-${name}-menu.png` });
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Confirm dialog" }).click();
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${out}/${scheme}-${name}-dialog.png` });
    }
    if (page.errors.length) console.log(scheme, name, page.errors);
    await page.context().close();
  }
}
await browser.close();
