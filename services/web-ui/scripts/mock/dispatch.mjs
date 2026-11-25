// Prompt triggers for the new scenarios (checked before the original ones in mock-scenarios.mjs).
import { widgetScenario } from "./widgets.mjs";
import { formScenario } from "./forms.mjs";
import { researchScenario } from "./research.mjs";
import { writeArtifactScenario, writePageScenario } from "./files.mjs";
import { agentBrowse } from "./browser.mjs";
import { loginScenario } from "./vault.mjs";

/** @returns {Promise<boolean>} true when the prompt was handled. */
export async function newScenarios(text, c) {
  if (/\bresearch\b/i.test(text) || c.body.research === true) return researchScenario(c);
  if (/\bbrowse\b/i.test(text)) {
    await c.tok("Opening the page in the browser.\n");
    await agentBrowse(c, /\bdocs\b/i.test(text) ? "docs.dot.local" : "news.example.org");
    await c.tok("Read the page; it lists three links.");
    return true;
  }
  if (/\bsign in\b/i.test(text)) return loginScenario(c);
  if (/\bwrite artifact\b/i.test(text)) return writeArtifactScenario(c);
  if (/\bwrite page\b/i.test(text)) return writePageScenario(c);
  if (/\bform\b/i.test(text)) return formScenario(c);
  if (await widgetScenario(text, c)) return true;
  if (/think/i.test(text)) {
    await c.thinkFor(c.ultra ? 8000 : 6500);
    await c.tok(`I thought it through (${c.ultra ? "max" : c.effort} effort). The short answer: it depends on the constraints, and the simplest option wins.`);
    return true;
  }
  return false;
}
