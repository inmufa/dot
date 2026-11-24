// Fixtures for the mock backend (shapes from packages/dot-contracts). `worst` swaps in break-ui data.
const iso = (min = 0) => new Date(Date.now() + min * 60_000).toISOString();
const LONG = "very-long-unbroken-name-".repeat(9);

export function seed(worst) {
  const tasks = worst
    ? Array.from({ length: 100 }, (_, i) => ({ id: `T${String(i).padStart(9, "0")}`, subject: i % 9 === 0 ? `${LONG}${i}` : `Step ${i} Привет Oʻzbek 🙂`, description: i % 5 === 0 ? "d".repeat(900) : "", status: ["pending", "in_progress", "completed"][i % 3], blocked_by: i > 3 ? [`T${String(i - 1).padStart(9, "0")}`, `T${String(i - 2).padStart(9, "0")}`, `T${String(i - 3).padStart(9, "0")}`] : [], created_at: iso(-i), updated_at: iso(-i) }))
    : [
        { id: "TAB12CD34", subject: "Read the project layout", description: "", status: "completed", blocked_by: [] },
        { id: "TAB12CD35", subject: "Write the failing test for logging setup", description: "Cover verbose and quiet modes.", status: "in_progress", blocked_by: ["TAB12CD34"] },
        { id: "TAB12CD36", subject: "Implement setup_logging()", description: "", status: "pending", blocked_by: ["TAB12CD35"] },
        { id: "TAB12CD37", subject: "Wire it into main()", description: "", status: "pending", blocked_by: ["TAB12CD36", "TAB12CD35"] },
        { id: "TAB12CD38", subject: "Update the README", description: "", status: "pending", blocked_by: [] },
      ].map((t) => ({ ...t, created_at: iso(-30), updated_at: iso(-5) }));
  const memory = worst
    ? Array.from({ length: 200 }, (_, i) => ({ id: `M${String(i).padStart(9, "0")}`, name: i % 11 === 0 ? `${LONG}${i}` : `Fact ${i} about the build`, description: i % 4 === 0 ? "A description that goes on. ".repeat(7) : "", kind: ["user", "feedback", "project", "reference"][i % 4], body: i % 3 === 0 ? "b".repeat(1500) : `Body of fact ${i}.\nSecond line.`, updated_at: iso(-i * 7) }))
    : [
        { id: "MA1B2C3D4", name: "Prefers uv over pip", description: "Python tooling", kind: "user", body: "Always run Python through uv. Never bare python or pip.", updated_at: iso(-3000) },
        { id: "MA1B2C3D5", name: "Tests live in tests/unit", description: "", kind: "project", body: "pytest, one file per module. Fixtures in conftest.py.", updated_at: iso(-900) },
        { id: "MA1B2C3D6", name: "No em dashes in prose", description: "Style rule", kind: "feedback", body: "Use a plain hyphen.", updated_at: iso(-90) },
      ];
  const mcp = [
    { name: "filesystem", transport: "stdio", scope: "user", status: "connected", tool_count: worst ? 50 : 6, trusted: true, error: null },
    { name: "project-db", transport: "stdio", scope: "project", status: "needs_trust", tool_count: 0, trusted: false, error: null },
    { name: "search-api", transport: "http", scope: "user", status: "failed", tool_count: 0, trusted: true, error: "Connection refused: http://127.0.0.1:9/mcp" },
    ...(worst ? [{ name: LONG, transport: "sse", scope: "project", status: "connecting", tool_count: 3, trusted: true, error: "E".repeat(700) }] : []),
  ];
  const run = (status, m) => ({ started_at: iso(m), finished_at: iso(m + 1), status, session_id: "S0000000AB", detail: "" });
  const schedules = [
    { id: "JB00000001", kind: "builtin", cron: "30 3 * * *", prompt: "memory.consolidate", enabled: true, created_at: iso(-9999), last_run_at: iso(-600), next_run_at: iso(800), last_status: "ok", runs: [run("ok", -600)] },
    { id: "JB00000002", kind: "builtin", cron: "45 4 * * 0", prompt: "logs prune", enabled: true, created_at: iso(-9999), last_run_at: null, next_run_at: iso(4000), last_status: null, runs: [] },
    { id: "JU00000001", kind: "user", cron: "0 9 * * mon-fri", prompt: "Summarize yesterday's commits and open issues.", enabled: true, created_at: iso(-500), last_run_at: iso(-300), next_run_at: iso(600), last_status: "failed", runs: [run("failed", -300)] },
    ...(worst ? [{ id: "JU00000002", kind: "user", cron: "*/7 1-5/2 29-31 feb,mar 7", prompt: "p".repeat(900), enabled: false, created_at: iso(-50), last_run_at: null, next_run_at: null, last_status: null, runs: [] }] : []),
  ];
  const tools = [
    ["Read", "Read a file from the workspace.", false, false], ["Write", "Write a file.", false, true], ["Edit", "Replace text in a file.", false, true],
    ["Bash", "Run a shell command in the sandbox.", false, true], ["Grep", "Search file contents.", false, false], ["Glob", "Find files by pattern.", false, false],
    ["WebSearch", "Search the web through SearXNG.", false, false], ["WebFetch", "Fetch a URL and return markdown.", false, false],
    ["Agent", "Run a subagent.", false, true], ["ToolSearch", "Find and load deferred tools.", false, false],
    ["Memory", "Add, update or delete memory facts.", true, true], ["CronCreate", "Create a scheduled prompt.", true, true], ["BrowserClick", "Click an element.", true, true],
  ].map(([name, description, deferred, mutating]) => ({ name, description, deferred, mutating, needs_approval: false, source: "builtin", input_schema: {} }));
  const mcpTools = Array.from({ length: worst ? 50 : 6 }, (_, i) => ({ name: `mcp__filesystem__tool_${i}`, description: i % 7 === 0 ? "Long description. ".repeat(20) : "Read or write via the filesystem server.", deferred: true, mutating: i % 2 === 0, needs_approval: i % 5 === 0, source: "mcp", input_schema: {} }));
  return { tasks, memory, mcp, schedules, tools: [...tools, ...mcpTools] };
}

export const PLAN = `## Plan: add logging

1. Add \`setup_logging(verbose)\` in \`src/app.py\`.
2. Call it from \`main()\` before \`run(args)\`.
3. Cover both modes in \`tests/unit/test_logging.py\`.

**Risks**
- Existing tests capture stdout; keep logs on stderr.

\`\`\`python
def setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
\`\`\`
`;
