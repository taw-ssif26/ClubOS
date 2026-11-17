import type { NextConfig } from "next";

const API = process.env.API_URL || "http://localhost:8000";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Same-origin proxy: the session cookie stays first-party and there is no CORS surface.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/:path*` },
      { source: "/media/:path*", destination: `${API}/media/:path*` },
    ];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        // Baseline CSP. Next.js needs inline scripts for hydration, so script-src stays permissive; these directives still
        // block framing, plugin content, base-tag hijacking and form posts to other origins.
        { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'" },
      ],
    }];
  },
};
export default config;
