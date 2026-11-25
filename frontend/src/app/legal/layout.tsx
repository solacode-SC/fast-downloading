import type { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "Terms & Legal Notice",
  description:
    "FastDL terms of use, public non-DRM media scope, automatic 30-minute file purge, and privacy guarantees.",
  alternates: {
    canonical: "/legal",
  },
};

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
