import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SkyFleet Ops",
  description: "AI-powered drone delivery fleet command center",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ops-bg text-slate-200">{children}</body>
    </html>
  );
}
