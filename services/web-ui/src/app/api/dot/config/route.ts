import { serverEnv } from "@/lib/server/env";

export const dynamic = "force-dynamic";

/** Public, token-free view of the server config: where the backend lives. */
export function GET(): Response {
  const env = serverEnv();
  return Response.json({
    backend: env.backend ? `${env.backend.protocol}//${env.backend.host}` : null,
    configured: env.token.length > 0,
  });
}
