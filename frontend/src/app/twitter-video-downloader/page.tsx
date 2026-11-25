import type { Metadata } from "next";
import React from "react";
import { DownloaderApp } from "@/components/DownloaderApp";
import { PlatformLandingView } from "@/components/PlatformLandingView";
import { buildPlatformJsonLd, buildPlatformMetadata, PLATFORM_SEO } from "@/lib/seo";

export const metadata: Metadata = buildPlatformMetadata("x");

export default function TwitterVideoDownloaderPage() {
  const cfg = PLATFORM_SEO.x;
  const jsonLd = buildPlatformJsonLd("x");

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <DownloaderApp
        initialPlatform="x"
        hideHomeFaq
        heroOverride={{
          pill: cfg.heroPill,
          titleLine1: cfg.heroTitleLine1,
          titleLine2: cfg.heroTitleLine2,
          subtitle: cfg.heroSubtitle,
          techSub: cfg.heroTechSub,
          placeholder: cfg.placeholder,
        }}
      />
      <PlatformLandingView platform="x" />
    </>
  );
}
