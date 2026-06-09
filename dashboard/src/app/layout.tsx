import type { Metadata } from 'next';
import { Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/lib/toast';
import { AppStateProvider } from '@/lib/components/AppStateProvider';
import { MotionProvider } from '@/lib/components/MotionProvider';
import './globals.css';

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-jakarta',
  weight: ['300', '400', '500', '600', '700', '800'],
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
    <html lang="en" suppressHydrationWarning className={`${plusJakartaSans.variable} ${jetbrainsMono.variable}`}>
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
