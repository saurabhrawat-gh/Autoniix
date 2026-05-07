import type { Metadata } from 'next';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/lib/toast';
import { AppStateProvider } from '@/lib/components/AppStateProvider';
import { MotionProvider } from '@/lib/components/MotionProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'YouTube Automation',
  description: 'Admin panel for YouTube content automation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen">
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
