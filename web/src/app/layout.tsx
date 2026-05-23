import type { Metadata, Viewport } from 'next'
import localFont from 'next/font/local'
import { JetBrains_Mono } from 'next/font/google'
import CursorSpotlight from '@/components/ui/CursorSpotlight'
import ScrollProgress from '@/components/ui/ScrollProgress'
import BackToTop from '@/components/ui/BackToTop'
import { ThemeProvider } from '@/components/ui/ThemeProvider'
import './globals.css'

const googleSansFlex = localFont({
  src: '../../public/fonts/GoogleSansFlex.ttf',
  variable: '--font-google-sans',
  weight: '100 900',
  display: 'swap',
})

const cattalague = localFont({
  src: '../../public/fonts/Cattalague.ttf',
  variable: '--font-cattalague',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500', '600'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Autoniix — AI Content Automation',
  description:
    'Autoniix orchestrates AI to research, script, voice, render and publish content — across every platform, at any scale. Your content empire, fully automated.',
  keywords: ['AI content automation', 'YouTube automation', 'content creation AI', 'automated video production'],
  authors: [{ name: 'Autoniix' }],
  creator: 'Autoniix',
  metadataBase: new URL('https://autoniix.com'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://autoniix.com',
    title: 'Autoniix — AI Content Automation',
    description: 'Research, script, voice, render, publish. Your content empire, fully automated.',
    siteName: 'Autoniix',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Autoniix — AI Content Automation',
    description: 'Research, script, voice, render, publish. Your content empire, fully automated.',
  },
  robots: {
    index: true,
    follow: true,
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#0A0A0F',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${googleSansFlex.variable} ${cattalague.variable} ${jetbrainsMono.variable}`}
    >
      <body className="antialiased font-sans transition-colors duration-300">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange={false}
        >
          <ScrollProgress />
          <CursorSpotlight />
          {children}
          <BackToTop />
        </ThemeProvider>
      </body>
    </html>
  )
}
