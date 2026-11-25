// Character candidates: injects throwaway CSS on the real UI and shoots home + chat. Usage: node scripts/character.mjs [port] [outDir]
import { mkdirSync } from "node:fs";
import { launch, newPage, VIEWPORTS } from "./pw.mjs";

const [, , port = "3204", dir = "shots/audit/character"] = process.argv;
mkdirSync(dir, { recursive: true });
const CSS = {
  base: "",
  A_logbook: `
  .column{max-width:54rem!important;margin-left:clamp(1rem,6vw,5rem)!important;margin-right:auto!important}
  .turns{counter-reset:t;border-left:1px solid var(--border);margin-left:4.5rem;padding-left:1.75rem;position:relative}
  .turn{position:relative;counter-increment:t}
  .turn::before{content:"14:" counter(t,decimal-leading-zero);position:absolute;left:-6.6rem;top:.2rem;font:500 12px var(--ff-mono);color:var(--text-faint)}
  .turn::after{content:"";position:absolute;left:calc(-1.75rem - 3.5px);top:.5rem;width:6px;height:6px;border-radius:50%;background:var(--accent)}
  .turn-user{justify-items:start!important}
  .bubble{background:none!important;padding:0!important;border-radius:0!important;font-weight:600;max-width:none!important}
  .turn-assistant{max-width:40rem}
  .composer-card{border-radius:6px!important;background:var(--surface)!important;box-shadow:inset 0 -2px 0 var(--accent)!important}
  .sb-session{border-radius:0!important;border-bottom:1px dotted var(--border);font-family:var(--ff-mono);font-size:12.5px}
  .sb-group{font-family:var(--ff-mono);font-weight:400!important;letter-spacing:.02em}
  .home-top{justify-items:start!important;text-align:left!important;padding-left:clamp(1rem,10vw,9rem)!important}
  .home-title{font-weight:300!important;font-size:2.4rem!important}
  .home-below{justify-items:start!important;padding-left:clamp(1rem,10vw,9rem)!important}
  .main[data-home="true"] .dock{transform:translateY(calc(-50dvh + 6rem))!important}
  .main[data-home="true"] .dock .column{margin-left:clamp(1rem,10vw,9rem)!important}`,
  B_round: `
  :root{--r-card:26px;--r-bubble:26px;--r-composer:32px}
  .bubble{background:var(--fill-active)!important;border-radius:26px!important}
  .turn-assistant .prose{font-size:1.06rem}
  .composer-card{border-radius:32px!important;box-shadow:var(--elev-1)!important}
  .sb-session{border-radius:999px!important}
  .home-title{font-weight:800!important;font-size:2.6rem!important}
  .dot{width:14px!important;height:14px!important}`,
  C_matrix: `
  :root{--r-card:2px;--r-bubble:2px;--r-composer:2px;--r-sm:2px;--r-ctl:2px;--ff-sans:var(--ff-mono)}
  body{font-family:var(--ff-mono)!important}
  .main{background-image:radial-gradient(circle at 1px 1px,color-mix(in srgb,var(--text) 14%,transparent) 1px,transparent 0);background-size:22px 22px}
  .bubble{background:none!important;box-shadow:inset 0 0 0 1px var(--text-faint)!important;border-radius:2px!important}
  .composer-card{border-radius:2px!important;box-shadow:inset 0 0 0 1px var(--text)!important}
  .sb-session{border-radius:2px!important}
  .sb-group,.home-recent h2{text-transform:uppercase;letter-spacing:.12em}
  .home-title{font-weight:500!important;text-transform:uppercase;font-size:1.6rem!important;letter-spacing:.04em}`,
};
const browser = await launch();
for (const [name, css] of Object.entries(CSS)) {
  const page = await newPage(browser, { viewport: VIEWPORTS.desktop, scheme: "light" });
  await page.goto(`http://127.0.0.1:${port}`);
  await page.waitForTimeout(1500);
  if (css) await page.addStyleTag({ content: css });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${dir}/${name}-home.png` });
  const box = page.getByRole("combobox", { name: "Message" });
  await box.fill("show me code"); await box.press("Enter");
  await page.waitForTimeout(4500);
  await page.screenshot({ path: `${dir}/${name}-chat.png` });
  await page.context().close();
}
await browser.close();
