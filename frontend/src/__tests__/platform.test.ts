import { describe, expect, it } from "vitest";
import { detectClientPlatform, extractSharedUrl } from "@/lib/platform";

describe("detectClientPlatform", () => {
  it("detects supported platforms and short links", () => {
    expect(detectClientPlatform("https://www.youtube.com/watch?v=jNQXAC9IVRw")).toBe("youtube");
    expect(detectClientPlatform("https://youtu.be/jNQXAC9IVRw")).toBe("youtube");
    expect(detectClientPlatform("https://x.com/NASA/status/123456")).toBe("x");
    expect(detectClientPlatform("https://twitter.com/NASA/status/123456")).toBe("x");
    expect(detectClientPlatform("https://www.instagram.com/reel/abc123/")).toBe("instagram");
    expect(detectClientPlatform("https://fb.watch/xyz/")).toBe("facebook");
  });

  it("rejects unsupported hosts", () => {
    expect(detectClientPlatform("https://example.com/video")).toBeNull();
    expect(detectClientPlatform("https://evil-youtube.com/watch")).toBeNull();
    expect(detectClientPlatform("")).toBeNull();
  });
});

describe("extractSharedUrl", () => {
  it("extracts url from direct ?url= or Web Share Target ?text=", () => {
    expect(extractSharedUrl(new URLSearchParams("url=https://youtu.be/jNQXAC9IVRw"))).toBe(
      "https://youtu.be/jNQXAC9IVRw"
    );
    expect(
      extractSharedUrl(new URLSearchParams("text=Check this out https://x.com/NASA/status/12345"))
    ).toBe("https://x.com/NASA/status/12345");
    expect(extractSharedUrl(new URLSearchParams("text=no link here"))).toBeNull();
  });
});
