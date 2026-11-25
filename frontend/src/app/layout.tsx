import type { Metadata, Viewport } from "next";
import Script from "next/script";
import React from "react";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { I18nProvider } from "@/lib/i18n";
import { SITE_NAME, SITE_TAGLINE, SITE_URL } from "@/lib/seo";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — ${SITE_TAGLINE}`,
    template: `%s | ${SITE_NAME}`,
  },
  description:
    "Fast, free, ad-free online video downloader for YouTube (4K 2160p HDR, Shorts, MP3 320kbps), X (Twitter) HD MP4 & GIFs, Instagram Reels & carousels, and Facebook Watch. 16x accelerated, zero re-encoding, no login required.",
  applicationName: SITE_NAME,
  keywords: [
    "fast video downloader",
    "free 4k video downloader",
    "youtube 4k video downloader",
    "youtube to mp4 1080p",
    "youtube to mp3 320kbps",
    "twitter x video downloader",
    "instagram reels downloader",
    "facebook video downloader",
    "online video downloader no ads",
    "privacy first video downloader",
    "download public videos online",
    "FastDL",
  ],
  authors: [{ name: "Solayman Builds", url: SITE_URL }],
  creator: "Solayman Builds",
  publisher: SITE_NAME,
  category: "multimedia",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description:
      "Download public 4K/HD videos, MP3 320 kbps audio, and SRT subtitles from YouTube, X (Twitter), Instagram, and Facebook. 16x accelerated, zero re-encoding, no ads, no login.",
    url: SITE_URL,
    siteName: SITE_NAME,
    type: "website",
    locale: "en_US",
    alternateLocale: ["fr_FR", "ar_AR"],
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: `${SITE_NAME} — Free 4K Video Downloader for YouTube, X, Instagram & Facebook`,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description:
      "Free, ad-free 4K video downloader for YouTube, X (Twitter), Instagram Reels, and Facebook. 16x parallel speed, zero re-encoding, no login.",
    images: ["/opengraph-image"],
  },
  robots: {
    index: true,
    follow: true,
    nocache: false,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icon.svg",
    apple: "/icon-maskable.svg",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#B8FF01" },
    { media: "(prefers-color-scheme: dark)", color: "#09090D" },
  ],
};

const themeInitScript = `
(function(){
  try {
    var mode = localStorage.getItem('fastdl_theme') || 'light';
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (mode === 'dark' || (mode === 'system' && prefersDark)) {
      document.documentElement.classList.add('dark');
    }
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://watcher.solaymanbuilds.com" />
        <link
          rel="alternate"
          type="text/plain"
          href="/llms.txt"
          title="FastDL LLM & AI Documentation"
        />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Cairo:wght@500;700;800;900&family=Inter:wght@500;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap"
          rel="stylesheet"
        />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="flex min-h-screen flex-col">
        <I18nProvider>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </I18nProvider>
        <Script
          src="https://watcher.solaymanbuilds.com/script.js"
          data-website-id="2545884d-703b-4592-9828-48fccab32ee2"
          data-domains="fastdownloading.solaymanbuilds.com,www.fastdownloading.solaymanbuilds.com"
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
