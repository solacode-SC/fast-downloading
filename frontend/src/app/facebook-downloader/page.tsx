import type { Metadata } from "next";
import React from "react";
import { DownloaderApp } from "@/components/DownloaderApp";
import { PlatformLandingView } from "@/components/PlatformLandingView";
import { buildPlatformJsonLd, buildPlatformMetadata, PLATFORM_SEO } from "@/lib/seo";

export const metadata: Metadata = buildPlatformMetadata("facebook");

export default function FacebookDownloaderPage() {
  const cfg = PLATFORM_SEO.facebook;
  const jsonLd = buildPlatformJsonLd("facebook");

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <DownloaderApp
        initialPlatform="facebook"
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
      <PlatformLandingView platform="facebook" />
    </>
  );
}
