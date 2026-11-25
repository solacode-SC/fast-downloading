import { ImageResponse } from "next/og";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        backgroundColor: "#EAE8E1",
        border: "14px solid #000000",
        padding: "56px",
        fontFamily: "sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            backgroundColor: "#B8FF01",
            border: "4px solid #000000",
            padding: "12px 24px",
            fontSize: 30,
            fontWeight: 900,
            color: "#000000",
          }}
        >
          {"</> FASTDL"}
        </div>
        <div
          style={{
            display: "flex",
            backgroundColor: "#7A5AF8",
            border: "4px solid #000000",
            padding: "12px 22px",
            fontSize: 22,
            fontWeight: 900,
            color: "#FFFFFF",
          }}
        >
          16X ACCELERATED · ZERO ADS
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "18px",
        }}
      >
        <div
          style={{
            fontSize: 76,
            fontWeight: 900,
            lineHeight: 1.02,
            color: "#000000",
            letterSpacing: "-2px",
          }}
        >
          FREE 4K VIDEO DOWNLOADER
        </div>
        <div
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: "#27272A",
          }}
        >
          YouTube 4K HDR & MP3 320K · X / Twitter HD · Instagram Reels · Facebook Watch
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", gap: "14px" }}>
          {["YOUTUBE", "X / TWITTER", "INSTAGRAM", "FACEBOOK"].map((label, idx) => (
            <div
              key={label}
              style={{
                display: "flex",
                backgroundColor: idx % 2 === 0 ? "#FF90E8" : "#FFFFFF",
                border: "4px solid #000000",
                padding: "10px 18px",
                fontSize: 20,
                fontWeight: 900,
                color: "#000000",
              }}
            >
              {label}
            </div>
          ))}
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 900,
            color: "#000000",
          }}
        >
          fastdownloading.solaymanbuilds.com
        </div>
      </div>
    </div>,
    { ...size }
  );
}
