import type { Metadata } from 'next';
import localFont from 'next/font/local';
import { JetBrains_Mono } from 'next/font/google';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/lib/toast';
import { AppStateProvider } from '@/lib/components/AppStateProvider';
import { MotionProvider } from '@/lib/components/MotionProvider';
import './globals.css';

const satoshi = localFont({
  src: [
    { path: '../../public/fonts/Satoshi-Variable.woff2', style: 'normal' },
    { path: '../../public/fonts/Satoshi-VariableItalic.woff2', style: 'italic' },
  ],
  variable: '--font-sans',
  weight: '300 900',
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
  icons: {
    icon: [
      { url: '/favicon-dark.png', media: '(prefers-color-scheme: dark)', type: 'image/png', sizes: '64x64' },
      { url: '/favicon-light.png', media: '(prefers-color-scheme: light)', type: 'image/png', sizes: '64x64' },
    ],
    shortcut: '/favicon-dark.png',
    apple: '/favicon-dark.png',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${satoshi.variable} ${jetbrainsMono.variable}`}>
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
