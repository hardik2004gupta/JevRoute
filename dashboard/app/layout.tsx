import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "JevRoute — Measuring the Economics of System-One Intelligence",
  description:
    "A reproducible benchmark for measuring the latency, cost, reliability, and control-plane economics of structured AI decisions.",
  openGraph: {
    title: "JevRoute — Measuring the Economics of System-One Intelligence",
    description:
      "A reproducible benchmark for measuring the latency, cost, reliability, and control-plane economics of structured AI decisions.",
    type: "website",
    siteName: "JevRoute",
  },
  twitter: {
    card: "summary",
    title: "JevRoute — Measuring the Economics of System-One Intelligence",
    description:
      "A reproducible benchmark for measuring the latency, cost, reliability, and control-plane economics of structured AI decisions.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${ibmPlexMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
