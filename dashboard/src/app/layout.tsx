import type { Metadata } from 'next';
import { ThemeProvider } from '@/lib/theme';
import './globals.css';

export const metadata: Metadata = {
  title: 'YouTube Automation',
  description: 'Admin panel for YouTube content automation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
