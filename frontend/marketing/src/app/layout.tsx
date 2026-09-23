import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { JetBrains_Mono } from "next/font/google";
import ScrollProgress from "@/components/ui/ScrollProgress";
import BackToTop from "@/components/ui/BackToTop";
import "./globals.css";

const satoshi = localFont({
  src: [
    { path: "../../public/fonts/Satoshi-Variable.woff2", style: "normal" },
    { path: "../../public/fonts/Satoshi-VariableItalic.woff2", style: "italic" },
  ],
  variable: "--font-sans",
  weight: "300 900",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Autoniix — AI Video Generation & Automation for YouTube",
  description:
    "Autoniix orchestrates AI to research, script, voice, render and publish YouTube content — Shorts and long-form, at any scale. Your YouTube empire, fully automated.",
  keywords: [
    "AI video generation",
    "AI content automation",
    "YouTube automation",
    "automated video production",
    "faceless YouTube channel",
  ],
  authors: [{ name: "Autoniix" }],
  creator: "Autoniix",
  metadataBase: new URL("https://autoniix.com"),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://autoniix.com",
    title: "Autoniix — AI Video Generation & Automation",
    description: "Research, script, voice, render, publish. Your content empire, fully automated.",
    siteName: "Autoniix",
  },
  twitter: {
    card: "summary_large_image",
    title: "Autoniix — AI Video Generation & Automation",
    description: "Research, script, voice, render, publish. Your content empire, fully automated.",
  },
  robots: { index: true, follow: true },
  icons: {
    icon: [{ url: "/favicon-dark.png", type: "image/png", sizes: "64x64" }],
    shortcut: "/favicon-dark.png",
    apple: "/favicon-dark.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0A0A0D",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${satoshi.variable} ${jetbrainsMono.variable}`}>
      <body className="ambient min-h-screen font-sans">
        <ScrollProgress />
        {children}
        <BackToTop />
      </body>
    </html>
  );
}
