import React from "react";
import { DownloaderApp } from "@/components/DownloaderApp";
import { buildHomeJsonLd } from "@/lib/seo";

export default function HomePage() {
  const jsonLd = buildHomeJsonLd();

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <DownloaderApp />
    </>
  );
}
