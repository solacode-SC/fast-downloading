import type { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "DMCA & Contact",
  description:
    "Report copyright or abuse concerns to FastDL. FastDL does not host or index videos permanently; transient files expire automatically.",
  alternates: {
    canonical: "/dmca",
  },
};

export default function DmcaLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
