// Browser tab e2e on its own: E2E_WEB / E2E_MOCK point at a running web + mock stack.
import { chromium } from "playwright-core";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { browserTab } from "./e2e-features.mjs";

const root = join(homedir(), ".cache/ms-playwright");
const exe = readdirSync(root).filter((x) => x.startsWith("chromium-")).map((d) => join(root, d, "chrome-linux64/chrome")).find(existsSync);
const WEB = process.env.E2E_WEB ?? "3199";
const b = await chromium.launch({ executablePath: exe, args: ["--no-sandbox"] });
try {
  const page = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await page.goto(`http://127.0.0.1:${WEB}/`);
  await page.getByRole("combobox", { name: "Message" }).waitFor();
  let n = 0;
  await browserTab(page, { name: "desk", phone: false, snap: async (s) => page.screenshot({ path: new URL(`../shots/browser/${s}.png`, import.meta.url).pathname }), ok: (c, m) => { if (!c) throw new Error(`FAIL: ${m}`); n++; console.log("ok", m); } });
  console.log(`browser e2e passed: ${n}`);
} catch (e) { console.error(e.message.split("\n").slice(0, 6).join("\n")); process.exitCode = 1; } finally { await b.close(); }
