import type { Metadata } from 'next';
import localFont from 'next/font/local';
import { JetBrains_Mono } from 'next/font/google';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/lib/toast';
import { AppStateProvider } from '@/lib/components/AppStateProvider';
import { MotionProvider } from '@/lib/components/MotionProvider';
import './globals.css';

// Match the marketing site (web/) exactly — one font system across the product.
const googleSansFlex = localFont({
  src: '../../public/fonts/GoogleSansFlex.ttf',
  variable: '--font-google-sans',
  weight: '100 900',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500', '600'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Autoniix',
  description: 'AI-powered content automation dashboard',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${googleSansFlex.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-screen font-sans">
        <MotionProvider>
          <ThemeProvider>
            <ToastProvider>
              <AppStateProvider>{children}</AppStateProvider>
            </ToastProvider>
          </ThemeProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
