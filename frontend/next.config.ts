import type { NextConfig } from "next";

const apiInternalOrigin = process.env.API_INTERNAL_URL || "http://api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/healthz",
        destination: `${apiInternalOrigin}/healthz`,
      },
      {
        source: "/readyz",
        destination: `${apiInternalOrigin}/readyz`,
      },
    ];
  },
};

export default nextConfig;
