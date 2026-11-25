// Dev stack for one worker: mock backend + `next dev`, on ports derived from a slot number.
// Usage: node scripts/dev-stack.mjs <slot 0-9>   -> web http://127.0.0.1:320<slot>, mock http://127.0.0.1:880<slot> (token mock-token)
// Several slots can run in parallel (separate .next-<slot> build dirs).
import { spawn } from "node:child_process";

const slot = Number(process.argv[2] ?? 0);
const WEB = 3200 + slot, MOCK = 8800 + slot;
const procs = [];
const run = (cmd, args, env) => procs.push(spawn(cmd, args, { env: { ...process.env, ...env }, stdio: ["ignore", "inherit", "inherit"] }));
run("node", ["scripts/mock-backend.mjs"], { MOCK_PORT: String(MOCK), MOCK_DELAY: process.env.MOCK_DELAY ?? "25" });
run("node", ["node_modules/next/dist/bin/next", "dev", "-H", "127.0.0.1", "-p", String(WEB)], {
  DOT_URL: `http://127.0.0.1:${MOCK}`, DOT_API_TOKEN: "mock-token", NEXT_DIST_DIR: `.next-${slot}`,
});
console.log(`web http://127.0.0.1:${WEB}  mock http://127.0.0.1:${MOCK}`);
const stop = () => { for (const p of procs) p.kill(); process.exit(0); };
process.on("SIGINT", stop); process.on("SIGTERM", stop);
