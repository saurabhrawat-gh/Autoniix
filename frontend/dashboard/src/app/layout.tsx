import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import { JetBrains_Mono } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { ThemeProvider } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";
import { AppStateProvider } from "@/lib/components/AppStateProvider";
import { MotionProvider } from "@/lib/components/MotionProvider";
import { QueryProvider } from "@/lib/components/QueryProvider";
import { FeatureFlagProvider } from "@/lib/components/FeatureFlagProvider";
import "./globals.css";
import "./themes.css";

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
  title: "Autoniix",
  description: "AI-powered content automation dashboard",
  icons: {
    icon: [
      { url: "/favicon-dark.png", media: "(prefers-color-scheme: dark)", type: "image/png", sizes: "64x64" },
      { url: "/favicon-light.png", media: "(prefers-color-scheme: light)", type: "image/png", sizes: "64x64" },
    ],
    shortcut: "/favicon-dark.png",
    apple: "/favicon-dark.png",
  },
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning className={`${satoshi.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-screen font-sans">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[9999] focus:px-4 focus:py-2 focus:rounded-lg focus:bg-surface-0 focus:border focus:border-accent focus:text-accent focus:text-sm focus:font-medium focus:shadow-elevated"
        >
          Skip to main content
        </a>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <QueryProvider>
            <FeatureFlagProvider>
              <MotionProvider>
                <ThemeProvider>
                  <ToastProvider>
                    <AppStateProvider>{children}</AppStateProvider>
                  </ToastProvider>
                </ThemeProvider>
              </MotionProvider>
            </FeatureFlagProvider>
          </QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
