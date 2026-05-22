import type { Metadata, Viewport } from 'next'
import { Inter, Bricolage_Grotesque, Instrument_Serif, JetBrains_Mono } from 'next/font/google'
import CursorSpotlight from '@/components/ui/CursorSpotlight'
import ScrollProgress from '@/components/ui/ScrollProgress'
import BackToTop from '@/components/ui/BackToTop'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['400', '500', '600', '700', '800'],
  display: 'swap',
})

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  variable: '--font-serif',
  weight: '400',
  style: ['normal', 'italic'],
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
      className={`dark ${inter.variable} ${bricolage.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-[#0A0A0F] text-white antialiased font-sans">
        <ScrollProgress />
        <CursorSpotlight />
        {children}
        <BackToTop />
      </body>
    </html>
  )
}
