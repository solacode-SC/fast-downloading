import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  const disallowed = ["/api/", "/healthz", "/readyz", "/metrics"];
  return {
    rules: [
      {
        userAgent: [
          "Googlebot",
          "Bingbot",
          "OAI-SearchBot",
          "ChatGPT-User",
          "GPTBot",
          "PerplexityBot",
          "ClaudeBot",
          "Claude-Web",
          "Google-Extended",
          "Applebot",
          "Applebot-Extended",
          "DuckDuckBot",
          "Yandex",
        ],
        allow: "/",
        disallow: disallowed,
      },
      {
        userAgent: "*",
        allow: "/",
        disallow: disallowed,
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
