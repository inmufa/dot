// Sidebar helpers shared by the e2e scripts.
const NAV_ROWS = ["Tasks", "Schedules", "Memory", "Skills"];
/** Nav rows live in the sidebar; Settings, MCP, Tools and Audit log in the account menu. */
export async function clickPanelRow(page, label) {
  if (NAV_ROWS.includes(label)) { await page.locator(".sb-navrow", { hasText: label }).click(); return; }
  await page.locator(".sb-full .sb-account").click();
  await page.getByRole("menuitem", { name: label }).click();
}
