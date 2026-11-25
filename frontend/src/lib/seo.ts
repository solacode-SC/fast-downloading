import type { Metadata } from "next";
import type { Platform } from "./api";

export const SITE_URL = "https://fastdownloading.solaymanbuilds.com";
export const SITE_NAME = "FastDL";
export const SITE_TAGLINE =
  "Free 4K Video Downloader for YouTube, X (Twitter), Instagram & Facebook";

export interface PlatformSeoConfig {
  platform: Platform;
  slug: string;
  name: string;
  metaTitle: string;
  metaDescription: string;
  keywords: string[];
  heroPill: string;
  heroTitleLine1: string;
  heroTitleLine2: string;
  heroSubtitle: string;
  heroTechSub: string;
  placeholder: string;
  summary: string;
  supportedFormats: { label: string; detail: string }[];
  steps: { title: string; text: string }[];
  highlights: { title: string; text: string }[];
  faqs: { q: string; a: string }[];
}

export const PLATFORM_SEO: Record<Platform, PlatformSeoConfig> = {
  youtube: {
    platform: "youtube",
    slug: "/youtube-downloader",
    name: "YouTube",
    metaTitle: "YouTube Video Downloader — Free 4K, 1080p MP4, Shorts & MP3 320kbps",
    metaDescription:
      "Download public YouTube videos, Shorts, and playlists in 4K 2160p HDR, 1080p MP4, M4A, or MP3 320 kbps with SRT subtitles. 16x accelerated, zero re-encoding, no ads, no login.",
    keywords: [
      "youtube video downloader",
      "download youtube 4k",
      "youtube to mp4 1080p",
      "youtube to mp3 320kbps",
      "youtube shorts downloader",
      "youtube subtitle downloader srt",
      "free youtube downloader no ads",
      "fast youtube downloader online",
    ],
    heroPill: "⚡ YOUTUBE 4K / HDR / MP3 320K · 16X ACCELERATED",
    heroTitleLine1: "YOUTUBE 4K",
    heroTitleLine2: "VIDEO DOWNLOADER",
    heroSubtitle:
      "Download public YouTube videos, Shorts, and playlists in 4K 2160p, 1080p MP4, or MP3 320 kbps.",
    heroTechSub:
      "16-connection parallel download with zero re-encoding (ffmpeg -c copy) and optional SRT subtitles.",
    placeholder: "https://www.youtube.com/watch?v=...",
    summary:
      "FastDL's YouTube Downloader extracts original video and audio streams directly from public YouTube links — including 4K 2160p 60fps HDR (VP9 / AV1), universally compatible H.264 MP4 for iPhone, macOS, Windows, and TVs, YouTube Shorts, playlists, and pure audio tracks in M4A or MP3 320 kbps.",
    supportedFormats: [
      {
        label: "4K / 1440p HDR",
        detail: "VP9 / AV1 up to 2160p 60fps merged losslessly in MKV/MP4",
      },
      { label: "1080p / 720p MP4", detail: "Universal H.264 (AVC1) + AAC with faststart metadata" },
      {
        label: "Audio M4A & MP3",
        detail: "Original AAC/M4A stream copy or 320 kbps / 192 kbps MP3",
      },
      {
        label: "SRT Subtitles & Cover",
        detail: "Optional manual or auto-generated SRT captions & HD thumbnail",
      },
    ],
    steps: [
      {
        title: "Copy any public YouTube URL",
        text: "Copy the link to a YouTube video, YouTube Short, youtu.be short link, or public playlist.",
      },
      {
        title: "Paste & pick your quality",
        text: "Paste into FastDL to inspect every resolution, codec, bitrate, HDR flag, and subtitle track — or click Quick Download for instant best quality.",
      },
      {
        title: "Save via 16x accelerated stream",
        text: "FastDL fetches streams in parallel, remuxes with ffmpeg -c copy on RAM-backed storage, and saves directly to your device.",
      },
    ],
    highlights: [
      {
        title: "16x Multi-Connection Speed",
        text: "Uses parallel HTTP Range acceleration (aria2c) to bypass slow single-connection bottlenecks on YouTube streams.",
      },
      {
        title: "Zero Re-Encoding Quality",
        text: "Audio and video are stream-copied with ffmpeg -c copy so you keep 100% of YouTube's original bitrate and HDR metadata.",
      },
      {
        title: "No Ads, Popups, or Extensions",
        text: "Works directly in Chrome, Safari, Firefox, Edge, iOS, and Android with zero ad redirects and zero account login.",
      },
    ],
    faqs: [
      {
        q: "Can I download YouTube videos in 4K 2160p 60fps with audio?",
        a: "Yes. YouTube serves 4K video and audio as separate DASH streams. FastDL downloads both in parallel and merges them losslessly using ffmpeg -c copy so you get a single 4K file with full audio.",
      },
      {
        q: "Which preset works best on iPhone, iPad, and QuickTime?",
        a: "Choose 'Best Compatible (MP4)' for H.264 + AAC inside an MP4 container with faststart enabled, guaranteed to play natively on iOS, macOS, Windows, Android, and smart TVs.",
      },
      {
        q: "Can I convert a YouTube video to MP3 320 kbps or original M4A?",
        a: "Yes. Select 'Audio Only (M4A)' for zero-loss original AAC audio or 'Audio Only (MP3 320 kbps)' for high-bitrate MP3 extraction.",
      },
      {
        q: "Does FastDL support YouTube Shorts and subtitles?",
        a: "Yes. Paste any youtube.com/shorts/ link to download in full HD without watermarks, and optionally select any available subtitle language to download a clean .srt file.",
      },
    ],
  },
  x: {
    platform: "x",
    slug: "/twitter-video-downloader",
    name: "X (Twitter)",
    metaTitle: "X (Twitter) Video Downloader — Free HD MP4 & GIF Saver",
    metaDescription:
      "Save public X (Twitter) videos and GIFs in highest-bitrate HD MP4 online for free. Supports x.com, twitter.com, and t.co links with no login, no watermarks, and no ads.",
    keywords: [
      "twitter video downloader",
      "x video downloader",
      "download x videos mp4",
      "save twitter gif as mp4",
      "twitter hd video downloader free",
      "download video from x.com",
    ],
    heroPill: "⚡ X / TWITTER HD MP4 & GIF SAVER · NO LOGIN",
    heroTitleLine1: "X / TWITTER",
    heroTitleLine2: "VIDEO DOWNLOADER",
    heroSubtitle: "Download public X (Twitter) videos and animated GIFs in crisp HD MP4.",
    heroTechSub: "Instant resolution for x.com, twitter.com, and t.co short links with zero ads.",
    placeholder: "https://x.com/username/status/...",
    summary:
      "FastDL's X (Twitter) Video Downloader extracts the highest-bitrate native MP4 video or GIF directly from any public post on x.com or twitter.com — including multi-video posts — without requiring an X account or API key.",
    supportedFormats: [
      {
        label: "Highest-Bitrate MP4",
        detail: "Automatically selects the crispest 1080p / 720p H.264 stream",
      },
      {
        label: "Twitter GIFs as MP4",
        detail: "Saves looping X GIF posts cleanly as compact MP4 files",
      },
      {
        label: "Multi-Video Posts",
        detail: "Inspect and download individual clips from multi-media posts",
      },
      { label: "Audio Extraction", detail: "Extract M4A or MP3 320 kbps audio from X video clips" },
    ],
    steps: [
      {
        title: "Copy the X / Twitter post link",
        text: "Tap Share -> Copy Link on any public post containing a video or GIF on x.com or twitter.com.",
      },
      {
        title: "Paste into FastDL",
        text: "FastDL instantly detects all available MP4 resolutions and bitrates, including t.co short links.",
      },
      {
        title: "Download HD MP4 immediately",
        text: "Click Quick Download or choose a specific resolution to save the clean MP4 to your phone or computer.",
      },
    ],
    highlights: [
      {
        title: "Ultra-Fast Metadata Resolve",
        text: "Resolves public X posts in under a second with automatic fallback so downloads stay reliable.",
      },
      {
        title: "Original Quality, No Watermarks",
        text: "Delivers the untouched MP4 stream with original audio and frame rate.",
      },
      {
        title: "Works on Mobile & Desktop",
        text: "Save X videos on iPhone (Safari), Android (Chrome), Windows, macOS, and Linux with no app required.",
      },
    ],
    faqs: [
      {
        q: "Does FastDL work with both x.com and twitter.com URLs?",
        a: "Yes. Paste x.com, twitter.com, mobile.twitter.com, or t.co links — FastDL normalizes them automatically.",
      },
      {
        q: "Can I download GIFs from X (Twitter)?",
        a: "Yes. X stores GIFs internally as looping MP4 videos, and FastDL saves them directly at original quality.",
      },
      {
        q: "Why can't a protected or private X account video be downloaded?",
        a: "FastDL only supports publicly accessible, non-DRM media and never bypasses private account permissions.",
      },
    ],
  },
  instagram: {
    platform: "instagram",
    slug: "/instagram-downloader",
    name: "Instagram",
    metaTitle: "Instagram Reels & Video Downloader — Free HD MP4 & Carousels",
    metaDescription:
      "Download public Instagram Reels, videos, and multi-video carousel posts in original HD MP4 with audio. Free, fast, privacy-first Instagram downloader with no login required.",
    keywords: [
      "instagram reels downloader",
      "instagram video downloader",
      "download instagram reels hd mp4",
      "instagram carousel video downloader",
      "save instagram video without login",
      "free ig reels downloader no watermark",
    ],
    heroPill: "⚡ INSTAGRAM REELS & CAROUSELS · HD MP4",
    heroTitleLine1: "INSTAGRAM REELS",
    heroTitleLine2: "VIDEO DOWNLOADER",
    heroSubtitle: "Save public Instagram Reels, feed videos, and multi-video carousels in HD MP4.",
    heroTechSub:
      "Original audio and video streams with zero watermarks, zero login, and zero popups.",
    placeholder: "https://www.instagram.com/reel/...",
    summary:
      "FastDL's Instagram Downloader lets you save public Instagram Reels, video posts, and multi-item carousel slides in original HD MP4 with audio — no Instagram login, no watermark, and no intrusive ads.",
    supportedFormats: [
      { label: "Instagram Reels HD", detail: "Full vertical 1080p MP4 with original audio track" },
      {
        label: "Carousel Picker",
        detail: "Select and download individual video items from multi-slide posts",
      },
      {
        label: "MP4 Universal",
        detail: "H.264 + AAC playback ready for iPhone, Android, and desktop",
      },
      {
        label: "Audio & Thumbnail",
        detail: "Extract Reel audio as M4A/MP3 or download the cover image",
      },
    ],
    steps: [
      {
        title: "Copy the Instagram Reel or post link",
        text: "Open any public Instagram Reel or video post, tap Share / three dots, and choose Copy Link.",
      },
      {
        title: "Paste & select item or format",
        text: "Paste the link into FastDL. For carousels, choose the exact slide from the item selector.",
      },
      {
        title: "Save clean HD MP4",
        text: "Download directly to your gallery or downloads folder without watermarks or re-encoding.",
      },
    ],
    highlights: [
      {
        title: "Multi-Slide Carousel Support",
        text: "Detects multi-video Instagram carousels and lets you pick which clip to download cleanly.",
      },
      {
        title: "No Instagram Account Needed",
        text: "Never asks for your Instagram credentials or cookies to save public Reels.",
      },
      {
        title: "Clean, Ad-Free Interface",
        text: "No fake download buttons, popunder tabs, or malware redirects.",
      },
    ],
    faqs: [
      {
        q: "Can I download Instagram Reels with sound in 1080p?",
        a: "Yes. FastDL automatically pairs the highest-resolution Reel video stream with its original AAC audio into a single MP4 file.",
      },
      {
        q: "Does FastDL support Instagram carousel posts with multiple videos?",
        a: "Yes. When you paste a public carousel link, FastDL lists each item so you can select and download the exact video you want.",
      },
      {
        q: "Can FastDL download private Instagram accounts or close-friends stories?",
        a: "No. FastDL strictly supports publicly accessible posts and Reels only.",
      },
    ],
  },
  facebook: {
    platform: "facebook",
    slug: "/facebook-downloader",
    name: "Facebook",
    metaTitle: "Facebook Video & Reels Downloader — Free HD & 1080p MP4",
    metaDescription:
      "Download public Facebook Watch videos, Facebook Reels, and fb.watch links in crisp HD 1080p MP4 online for free. Fast, private, no login and no software needed.",
    keywords: [
      "facebook video downloader",
      "facebook reels downloader",
      "download facebook watch video hd",
      "fb.watch downloader mp4",
      "facebook to mp4 1080p free",
      "save facebook video online",
    ],
    heroPill: "⚡ FACEBOOK WATCH & REELS · HD 1080P MP4",
    heroTitleLine1: "FACEBOOK VIDEO",
    heroTitleLine2: "& REELS DOWNLOADER",
    heroSubtitle:
      "Download public Facebook Watch videos, Reels, and fb.watch share links in HD MP4.",
    heroTechSub:
      "Automatic share-redirect resolution, stream-copied HD video + audio, and zero ads.",
    placeholder: "https://www.facebook.com/watch/?v=...",
    summary:
      "FastDL's Facebook Video Downloader resolves public facebook.com/watch, facebook.com/reel, /share/r/, /share/v/, and fb.watch links into crisp HD MP4 files or MP3 audio tracks with zero software installation.",
    supportedFormats: [
      {
        label: "HD 1080p / 720p MP4",
        detail: "Stream-copied HD video & AAC audio in universal MP4",
      },
      {
        label: "Facebook Reels & Share Links",
        detail: "Automatically unwraps /share/v/, /share/r/, and fb.watch URLs",
      },
      { label: "SD & Low-Data Options", detail: "Pick 480p SD when you want smaller file sizes" },
      {
        label: "Audio Extraction",
        detail: "Save speech, podcasts, or music from public videos as M4A or MP3",
      },
    ],
    steps: [
      {
        title: "Copy the public Facebook video link",
        text: "Click Share -> Copy Link on any public Facebook Watch video or Facebook Reel.",
      },
      {
        title: "Paste into FastDL",
        text: "FastDL resolves share redirects automatically and displays all available HD and SD formats.",
      },
      {
        title: "Download HD MP4",
        text: "Click Quick Download or choose your resolution to save directly to your device.",
      },
    ],
    highlights: [
      {
        title: "Handles Facebook Share Redirects",
        text: "Seamlessly resolves modern facebook.com/share/v/ and fb.watch short URLs that break older downloaders.",
      },
      {
        title: "HD Audio + Video Remuxing",
        text: "Merges separate HD video and audio tracks cleanly via ffmpeg -c copy so HD downloads always have sound.",
      },
      {
        title: "100% Browser-Based & Private",
        text: "No Facebook login required and temporary files are auto-purged within 30 minutes.",
      },
    ],
    faqs: [
      {
        q: "Does FastDL work with fb.watch and facebook.com/share/r/ links?",
        a: "Yes. FastDL safely follows Facebook redirect URLs and normalizes /reels/, /share/v/, /share/r/, and fb.watch links automatically.",
      },
      {
        q: "Why do some Facebook HD downloaders produce silent videos, and how does FastDL avoid that?",
        a: "Facebook serves 1080p HD streams as separate video and audio tracks. FastDL automatically downloads both and merges them with ffmpeg -c copy so your MP4 always has crystal-clear sound.",
      },
      {
        q: "Can I download videos from private Facebook groups?",
        a: "No. FastDL only accesses publicly visible Facebook Watch videos and Reels.",
      },
    ],
  },
};

export function buildPlatformMetadata(platform: Platform): Metadata {
  const cfg = PLATFORM_SEO[platform];
  const url = `${SITE_URL}${cfg.slug}`;
  return {
    title: cfg.metaTitle,
    description: cfg.metaDescription,
    keywords: cfg.keywords,
    alternates: {
      canonical: cfg.slug,
    },
    openGraph: {
      title: `${cfg.metaTitle} | ${SITE_NAME}`,
      description: cfg.metaDescription,
      url,
      siteName: SITE_NAME,
      type: "website",
      locale: "en_US",
      images: [
        {
          url: `${SITE_URL}/opengraph-image`,
          width: 1200,
          height: 630,
          alt: `${SITE_NAME} — ${cfg.name} Video Downloader`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${cfg.metaTitle} | ${SITE_NAME}`,
      description: cfg.metaDescription,
      images: [`${SITE_URL}/opengraph-image`],
    },
  };
}

export function buildHomeJsonLd(): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${SITE_URL}/#website`,
        url: SITE_URL,
        name: SITE_NAME,
        alternateName: ["FastDL Video Downloader", "Fast Downloading"],
        description:
          "Fast, free, ad-free online downloader for public, non-DRM videos from YouTube (4K HDR, Shorts, MP3 320kbps), X (Twitter), Instagram Reels, and Facebook Watch.",
        inLanguage: ["en", "fr", "ar"],
      },
      {
        "@type": "Organization",
        "@id": `${SITE_URL}/#organization`,
        name: SITE_NAME,
        url: SITE_URL,
        logo: {
          "@type": "ImageObject",
          url: `${SITE_URL}/icon.svg`,
        },
      },
      {
        "@type": "WebApplication",
        "@id": `${SITE_URL}/#webapp`,
        name: "FastDL — Public Video Downloader",
        url: SITE_URL,
        applicationCategory: "MultimediaApplication",
        operatingSystem: "Any (Web, Windows, macOS, Linux, iOS, Android)",
        browserRequirements: "Requires JavaScript. Works in Chrome, Safari, Firefox, and Edge.",
        isAccessibleForFree: true,
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "USD",
        },
        featureList: [
          "YouTube 4K 2160p HDR, 1440p, 1080p MP4, Shorts, and playlist downloads",
          "X (Twitter) highest-bitrate HD MP4 and GIF video downloads",
          "Instagram Reels, videos, and multi-video carousel downloads",
          "Facebook Watch, Reels, and fb.watch HD MP4 downloads",
          "Audio extraction in original M4A and MP3 320 kbps / 192 kbps",
          "Optional SRT subtitle and thumbnail downloads",
          "16-connection parallel download acceleration (aria2c) and zero re-encoding (ffmpeg -c copy)",
          "HTTP 206 Range resumable downloads with HMAC-SHA256 signed URLs",
          "Privacy-first: zero ads, zero popups, no login required, 30-minute automatic file purge",
          "Multi-language UI in English, French, and Arabic (RTL)",
        ],
      },
      {
        "@type": "HowTo",
        "@id": `${SITE_URL}/#howto`,
        name: "How to download public videos in 4K or MP3 using FastDL",
        description:
          "Download public videos from YouTube, X (Twitter), Instagram, or Facebook in 3 fast steps with no login or ads.",
        totalTime: "PT30S",
        step: [
          {
            "@type": "HowToStep",
            position: 1,
            name: "Paste a public video URL",
            text: "Copy any public video link from YouTube, X (Twitter), Instagram, or Facebook and paste it into FastDL.",
          },
          {
            "@type": "HowToStep",
            position: 2,
            name: "Choose resolution or audio format",
            text: "Click Analyze Formats to choose 4K 2160p, Compatible MP4, 1080p, 720p, M4A, MP3 320 kbps, or SRT subtitles — or click Quick Download for instant best quality.",
          },
          {
            "@type": "HowToStep",
            position: 3,
            name: "Save your stream-copied file",
            text: "FastDL accelerates the download in parallel, merges streams losslessly with ffmpeg -c copy, and saves the file directly to your device.",
          },
        ],
      },
      {
        "@type": "FAQPage",
        "@id": `${SITE_URL}/#faq`,
        mainEntity: [
          {
            "@type": "Question",
            name: "What is FastDL and which platforms are supported?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "FastDL (fastdownloading.solaymanbuilds.com) is a free, privacy-first online video downloader for public, non-DRM media from YouTube (4K/2160p, HDR, 60fps, Shorts, playlists), X / Twitter (HD MP4 and GIFs), Instagram (Reels, posts, and multi-video carousels), and Facebook (Watch and Reels). No signup, browser extension, or app install is needed.",
            },
          },
          {
            "@type": "Question",
            name: "Why is FastDL faster than other online video downloaders?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "FastDL uses 16-connection parallel HTTP acceleration (aria2c) and concurrent fragment fetching, merges video and audio directly on RAM-backed tmpfs with ffmpeg -c copy (zero quality-losing re-encoding), and delivers files via HTTP 206 Range streaming.",
            },
          },
          {
            "@type": "Question",
            name: "Can I download YouTube videos in 4K 60fps, 1080p MP4, or MP3 320 kbps?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "Yes. Paste any public YouTube link and choose Best Available (up to 4K 2160p HDR VP9/AV1), Best Compatible MP4 (H.264 + AAC for iPhone, macOS, Windows, and TVs), 1440p/1080p/720p/480p, original M4A audio, or MP3 at 320 kbps / 192 kbps. You can also include SRT subtitles and the video thumbnail.",
            },
          },
          {
            "@type": "Question",
            name: "How do I download X (Twitter), Instagram Reels, or Facebook videos without logging in?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "Copy any public post, Reel, or Watch link, paste it into FastDL, and click Quick Download or Analyze Formats. FastDL resolves public streams without asking for your social media password or login.",
            },
          },
          {
            "@type": "Question",
            name: "Is FastDL safe, private, and free of popups?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "Yes. FastDL has zero popups, zero adware, and no user accounts. Temporary files expire automatically after 30 minutes, your recent history stays strictly in your browser localStorage, and downloads use HMAC-signed URLs.",
            },
          },
          {
            "@type": "Question",
            name: "Can I download multiple videos in a row without refreshing?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "Yes. Simply paste a new link into the input box or click Paste / Download Another to immediately analyze and download your next video without reloading the page.",
            },
          },
        ],
      },
    ],
  };
}

export function buildPlatformJsonLd(platform: Platform): Record<string, unknown> {
  const cfg = PLATFORM_SEO[platform];
  const url = `${SITE_URL}${cfg.slug}`;
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: "FastDL Home",
            item: SITE_URL,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: `${cfg.name} Video Downloader`,
            item: url,
          },
        ],
      },
      {
        "@type": "WebApplication",
        name: `FastDL ${cfg.name} Video Downloader`,
        url,
        description: cfg.metaDescription,
        applicationCategory: "MultimediaApplication",
        operatingSystem: "Any (Web, Windows, macOS, Linux, iOS, Android)",
        isAccessibleForFree: true,
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "USD",
        },
      },
      {
        "@type": "HowTo",
        name: `How to download ${cfg.name} videos with FastDL`,
        totalTime: "PT20S",
        step: cfg.steps.map((s, idx) => ({
          "@type": "HowToStep",
          position: idx + 1,
          name: s.title,
          text: s.text,
        })),
      },
      {
        "@type": "FAQPage",
        mainEntity: cfg.faqs.map((item) => ({
          "@type": "Question",
          name: item.q,
          acceptedAnswer: {
            "@type": "Answer",
            text: item.a,
          },
        })),
      },
    ],
  };
}
