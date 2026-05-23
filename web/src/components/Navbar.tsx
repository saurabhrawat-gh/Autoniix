'use client'

import { useEffect, useState } from 'react'
import { Menu, X, Zap, Sun, Moon } from 'lucide-react'
import { useTheme } from 'next-themes'
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
  const [mounted, setMounted] = useState(false)
  const { theme, setTheme } = useTheme()

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? 'bg-white/80 dark:bg-[#08080F]/85 backdrop-blur-2xl border-b border-black/[0.06] dark:border-white/[0.07]'
          : 'bg-transparent'
      }`}
    >
      {/* Gradient border-bottom — only when scrolled */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px transition-opacity duration-500"
        style={{
          background: 'linear-gradient(90deg, transparent 0%, rgba(0,216,159,0.2) 30%, rgba(124,58,237,0.15) 70%, transparent 100%)',
          opacity: scrolled ? 1 : 0,
        }}
      />

      <nav className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00D89F] to-[#00A876] flex items-center justify-center transition-all duration-300 group-hover:shadow-[0_0_22px_rgba(0,216,159,0.55)] group-hover:scale-110">
            <Zap className="w-4 h-4 text-[#09090F] fill-[#09090F]" strokeWidth={2} />
          </div>
          <span className="t-headline" style={{ color: 'var(--text-primary)', fontSize: '1.0625rem', fontWeight: 500, letterSpacing: '-0.018em' }}>Autoniix</span>
        </a>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="relative px-4 py-2 t-body-sm hover:opacity-100 transition-colors duration-200 group"
              style={{ color: 'var(--text-secondary)' }}
            >
              {link.label}
              <span className="absolute bottom-0.5 left-4 right-4 h-px bg-gradient-to-r from-[#00D89F] to-[#7C3AED] scale-x-0 group-hover:scale-x-100 transition-transform duration-300 origin-center rounded-full" />
            </a>
          ))}
        </div>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">
          {/* Theme toggle */}
          {mounted && (
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-black/5 dark:hover:bg-white/8 transition-all duration-200"
              style={{ color: 'var(--text-secondary)' }}
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" strokeWidth={1.5} /> : <Moon className="w-4 h-4" strokeWidth={1.5} />}
            </button>
          )}
          <a
            href="https://dash.autoniix.com/login"
            className="t-body-sm transition-colors duration-150 px-3 py-2"
            style={{ color: 'var(--text-secondary)' }}
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
          {menuOpen ? <X className="w-5 h-5" strokeWidth={1.5} /> : <Menu className="w-5 h-5" strokeWidth={1.5} />}
        </button>
      </nav>

      {/* Mobile menu */}
      <div
        className={`md:hidden transition-all duration-300 overflow-hidden ${
          menuOpen ? 'max-h-screen opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="bg-white/95 dark:bg-[#08080F]/96 backdrop-blur-2xl border-b border-black/[0.06] dark:border-white/[0.07] px-6 py-6 flex flex-col gap-2">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] py-3 border-b border-black/5 dark:border-white/5 last:border-0 transition-colors text-base"
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </a>
          ))}
          <div className="pt-4 flex flex-col gap-3">
            <a
              href="https://dash.autoniix.com/login"
              className="text-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors py-2"
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
