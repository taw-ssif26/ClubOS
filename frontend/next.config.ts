import type { NextConfig } from "next";


const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // /api/* is handled by src/app/api/[...path]/route.ts (authenticated, retrying proxy). Images are public, cacheable GETs.
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
