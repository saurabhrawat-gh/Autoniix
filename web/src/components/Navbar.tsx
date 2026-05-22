'use client'

import { useEffect, useState } from 'react'
import { Menu, X, Zap } from 'lucide-react'
import GlowButton from './ui/GlowButton'

const NAV_LINKS = [
  { label: 'Features', href: '#features' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Docs', href: '#docs' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-[#0A0A0F]/80 backdrop-blur-xl border-b border-white/10 shadow-[0_1px_0_0_rgba(255,255,255,0.05)]'
          : 'bg-transparent border-b border-transparent'
      }`}
    >
      <nav className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00D89F] to-[#00A876] flex items-center justify-center shadow-[0_0_12px_rgba(0,216,159,0.4)] group-hover:shadow-[0_0_20px_rgba(0,216,159,0.5)] transition-shadow duration-200">
            <Zap className="w-4 h-4 text-[#0A0A0F] fill-[#0A0A0F]" />
          </div>
          <span className="font-display text-white font-bold text-lg tracking-tight">Autoniix</span>
        </a>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="relative px-4 py-2 text-sm text-white/60 hover:text-white transition-all duration-150 group"
            >
              {link.label}
              <span className="absolute bottom-1 left-4 right-4 h-px bg-[#00D89F] scale-x-0 group-hover:scale-x-100 transition-transform duration-200 origin-left rounded-full" />
            </a>
          ))}
        </div>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">
          <a
            href="https://dash.autoniix.com/login"
            className="text-sm text-white/60 hover:text-white/90 transition-colors duration-150 px-3 py-2"
          >
            Sign in
          </a>
          <GlowButton
            size="sm"
            onClick={() => window.open('https://dash.autoniix.com/register', '_blank')}
          >
            Get started free →
          </GlowButton>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-white/70 hover:text-white transition-colors p-2"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </nav>

      {/* Mobile menu */}
      <div
        className={`md:hidden transition-all duration-300 overflow-hidden ${
          menuOpen ? 'max-h-screen opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="bg-[#0A0A0F]/95 backdrop-blur-xl border-b border-white/10 px-6 py-6 flex flex-col gap-2">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-white/70 hover:text-white py-3 border-b border-white/5 last:border-0 transition-colors text-base"
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </a>
          ))}
          <div className="pt-4 flex flex-col gap-3">
            <a
              href="https://dash.autoniix.com/login"
              className="text-center text-white/60 hover:text-white transition-colors py-2"
            >
              Sign in
            </a>
            <GlowButton
              size="md"
              className="w-full justify-center"
              onClick={() => window.open('https://dash.autoniix.com/register', '_blank')}
            >
              Get started free →
            </GlowButton>
          </div>
        </div>
      </div>
    </header>
  )
}
