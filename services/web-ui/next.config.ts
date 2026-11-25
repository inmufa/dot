import type { NextConfig } from "next";

const dev = process.env.NODE_ENV !== "production";

// Nothing loads from, or talks to, any other origin. Pages are prerendered, so the inline
// bootstrap scripts need 'unsafe-inline'; eval is dev-only (React refresh).
const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${dev ? " ws: wss:" : ""}`,
  "media-src 'self' blob:",
  "worker-src 'self' blob:",
  "frame-src 'self'",
  "object-src 'none'",
  "form-action 'self'",
  "base-uri 'none'",
  "frame-ancestors 'none'",
].join("; ");

const PERMISSIONS = "camera=(), geolocation=(), payment=(), usb=(), microphone=(self)";

const config: NextConfig = {
  // Parallel dev servers (scripts/dev-stack.mjs) each get their own build dir.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: "standalone",
  poweredByHeader: false,
  // Compression buffers SSE frames; the proxy must stream untouched.
  compress: false,
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/((?!api/dot).*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: CSP },
          { key: "Permissions-Policy", value: PERMISSIONS },
        ],
      },
      {
        // session files are previewed in a sandboxed same-origin iframe
        source: "/api/dot/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
    ];
  },
};

export default config;
