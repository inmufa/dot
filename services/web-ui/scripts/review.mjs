// Screenshot review: node scripts/review.mjs <webPort> <outDir> [round]  (dev stack or next start must run)
import { mkdirSync } from "node:fs";
import { launch, newPage, VIEWPORTS } from "./pw.mjs";

const [, , port = "3201", dir = "shots/review"] = process.argv;
const base = `http://127.0.0.1:${port}`;
mkdirSync(dir, { recursive: true });
const browser = await launch();
for (const [vn, vp] of Object.entries(VIEWPORTS)) {
  for (const scheme of ["light", "dark"]) {
    const page = await newPage(browser, { viewport: vp, scheme });
    const shot = (n) => page.screenshot({ path: `${dir}/${vn}-${scheme}-${n}.png` });
    await page.goto(base);
    await page.waitForTimeout(900);
    await shot("1-home");
    const box = page.getByRole("combobox", { name: "Message" });
    await box.fill("show me widgets");
    await box.press("Enter");
    await page.waitForFunction(() => !document.querySelector(".topbar-label") || document.querySelector(".topbar-label").textContent === "Idle", null, { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(600);
    await shot("2-widgets");
    await box.fill("edit the app");
    await box.press("Enter");
    await page.waitForTimeout(1400);
    await shot("3-approval");
    if (page.errors.length) console.log(vn, scheme, page.errors.slice(0, 3));
    await page.context().close();
  }
}
await browser.close();
