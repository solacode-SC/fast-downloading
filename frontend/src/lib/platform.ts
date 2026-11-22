import type { Platform } from "./api";

const PLATFORM_MATCHERS: Array<{ platform: Platform; hosts: string[] }> = [
  { platform: "youtube", hosts: ["youtube.com", "youtu.be", "youtube-nocookie.com"] },
  { platform: "x", hosts: ["x.com", "twitter.com", "t.co", "fxtwitter.com", "vxtwitter.com"] },
  { platform: "instagram", hosts: ["instagram.com", "instagr.am"] },
  { platform: "facebook", hosts: ["facebook.com", "fb.watch", "fb.com", "fb.gg"] },
];

export function detectClientPlatform(input: string): Platform | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);
    const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
    for (const entry of PLATFORM_MATCHERS) {
      if (entry.hosts.some((h) => host === h || host.endsWith(`.${h}`))) {
        return entry.platform;
      }
    }
  } catch {
    return null;
  }
  return null;
}

export function extractSharedUrl(params: URLSearchParams): string | null {
  const direct = params.get("url")?.trim();
  if (direct && /^https?:\/\//i.test(direct)) return direct;
  const text = params.get("text")?.trim();
  if (text) {
    const match = text.match(/https?:\/\/[^\s]+/i);
    if (match) return match[0];
  }
  return null;
}

export const PLATFORM_META: Record<
  Platform,
  { name: string; code: string; spec: string; badgeClass: string }
> = {
  youtube: {
    name: "YouTube",
    code: "YT",
    spec: "4K · HDR · Shorts",
    badgeClass: "bg-brutal-pink text-black border-2 border-black",
  },
  x: {
    name: "X / Twitter",
    code: "X",
    spec: "HD MP4 · GIF",
    badgeClass: "bg-brutal-lime text-black border-2 border-black",
  },
  instagram: {
    name: "Instagram",
    code: "IG",
    spec: "Reels · Carousels",
    badgeClass: "bg-brutal-purple text-white border-2 border-black",
  },
  facebook: {
    name: "Facebook",
    code: "FB",
    spec: "Watch · Reels",
    badgeClass: "bg-white text-black border-2 border-black",
  },
};
