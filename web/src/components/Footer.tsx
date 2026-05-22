import { Zap } from 'lucide-react'

const footerLinks = {
  Product: ['Features', 'How it works', 'Pricing', 'Changelog'],
  Resources: ['Documentation', 'Blog', 'Status', 'Support'],
  Legal: ['Privacy Policy', 'Terms of Service', 'Cookie Policy'],
}

export default function Footer() {
  return (
    <footer className="border-t border-white/5 bg-black/20">
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-8">
        {/* Top row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-16">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <a href="/" className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00D89F] to-[#00A876] flex items-center justify-center shadow-[0_0_12px_rgba(0,216,159,0.3)]">
                <Zap className="w-4 h-4 text-[#0A0A0F] fill-[#0A0A0F]" />
              </div>
              <span className="font-display text-white font-bold text-lg tracking-tight">Autoniix</span>
            </a>
            <p className="text-white/40 text-sm leading-relaxed max-w-[220px]">
              AI-powered content automation. Research, script, voice, render, publish.
            </p>
            {/* Social */}
            <div className="flex items-center gap-3 mt-5">
              {[
                { name: 'X', href: 'https://twitter.com/autoniix', label: 'X (Twitter)' },
                { name: 'GH', href: 'https://github.com/autoniix', label: 'GitHub' },
                { name: 'YT', href: 'https://youtube.com/@autoniix', label: 'YouTube' },
              ].map((s) => (
                <a
                  key={s.name}
                  href={s.href}
                  aria-label={s.label}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-8 h-8 rounded-lg glass-card border border-white/8 flex items-center justify-center text-white/40 hover:text-white/70 hover:border-white/15 transition-all duration-150 text-xs font-bold font-mono"
                >
                  {s.name}
                </a>
              ))}
            </div>
          </div>

          {/* Link columns */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <p className="text-white/60 text-xs font-semibold uppercase tracking-wider mb-4">
                {category}
              </p>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link}>
                    <a
                      href="#"
                      className="text-white/38 hover:text-white/65 text-sm transition-colors duration-150"
                    >
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-8 border-t border-white/5">
          <p className="text-white/25 text-xs">
            © {new Date().getFullYear()} Autoniix. All rights reserved.
          </p>
          <p className="text-white/25 text-xs">
            Built with AI, for creators.
          </p>
        </div>
      </div>
    </footer>
  )
}
