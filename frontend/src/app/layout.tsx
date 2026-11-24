import type { Metadata, Viewport } from "next";
import React from "react";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "FastDL — Public Video Downloader",
  description:
    "Fast, privacy-first downloader for public, non-DRM videos from YouTube, X (Twitter), Instagram, and Facebook.",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icon.svg",
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
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link
        href="https://fonts.googleapis.com/css2?family=Cairo:wght@500;700;800;900&family=Inter:wght@500;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap"
        rel="stylesheet"
      />
      <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      <script
        defer
        src="https://watcher.solaymanbuilds.com/script.js"
        data-website-id="2545884d-703b-4592-9828-48fccab32ee2"
        data-domains="fastdownloading.solaymanbuilds.com"
      />
      </head>
      <body className="flex min-h-screen flex-col">
        <I18nProvider>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </I18nProvider>
      </body>
    </html>
  );
}
