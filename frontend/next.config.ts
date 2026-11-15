import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const configured = process.env.SPHEREX_BACKEND_URL?.trim();
    if (process.env.VERCEL && !configured) {
      throw new Error("Set SPHEREX_BACKEND_URL to the Render backend HTTPS origin in Vercel before building.");
    }
    const origin = new URL(configured || "http://127.0.0.1:8000");
    if (!['http:', 'https:'].includes(origin.protocol) || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/') {
      throw new Error("SPHEREX_BACKEND_URL must be an HTTP(S) origin without credentials, /api, a path, or a query.");
    }
    if (process.env.VERCEL && (origin.protocol !== 'https:' || ['localhost', '127.0.0.1', '[::1]'].includes(origin.hostname))) {
      throw new Error("Vercel requires a public HTTPS SPHEREX_BACKEND_URL, not localhost.");
    }
    const backendUrl = origin.origin;
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    root: process.cwd(),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
