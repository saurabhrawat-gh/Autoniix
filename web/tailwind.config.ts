import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'bg-base': '#0A0A0F',
        'bg-card': 'rgba(255,255,255,0.04)',
        'accent-green': '#00D89F',
        'accent-green-dim': '#00A876',
        'accent-purple': '#6645C1',
        'accent-blue': '#2563EB',
        'text-primary': '#FFFFFF',
        'text-secondary': 'rgba(255,255,255,0.65)',
        'text-muted': 'rgba(255,255,255,0.38)',
        'border-subtle': 'rgba(255,255,255,0.08)',
        'border-card': 'rgba(255,255,255,0.10)',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'Bricolage Grotesque', 'system-ui', 'sans-serif'],
        serif: ['var(--font-serif)', 'Instrument Serif', 'Georgia', 'serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'Fira Code', 'monospace'],
      },
      letterSpacing: {
        tight: '-0.022em',
        tighter: '-0.03em',
      },
      backgroundImage: {
        'glow-green': 'radial-gradient(ellipse at center, rgba(0,216,159,0.15) 0%, transparent 70%)',
        'glow-purple': 'radial-gradient(ellipse at center, rgba(102,69,193,0.15) 0%, transparent 70%)',
        'glow-blue': 'radial-gradient(ellipse at center, rgba(37,99,235,0.12) 0%, transparent 70%)',
        'hero-gradient': 'linear-gradient(135deg, rgba(0,216,159,0.08) 0%, transparent 50%, rgba(102,69,193,0.08) 100%)',
        'btn-primary': 'linear-gradient(135deg, #00D89F 0%, #00A876 100%)',
        'card-glass': 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
      },
      boxShadow: {
        'glow-sm': '0 0 12px rgba(0,216,159,0.25)',
        'glow-md': '0 0 24px rgba(0,216,159,0.20)',
        'glow-lg': '0 0 48px rgba(0,216,159,0.15)',
        'card': '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        'card-hover': '0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,216,159,0.2)',
        'purple-glow': '0 0 24px rgba(102,69,193,0.25)',
      },
      animation: {
        'float-slow': 'float 8s ease-in-out infinite',
        'float-medium': 'float 6s ease-in-out infinite 2s',
        'float-fast': 'float 5s ease-in-out infinite 1s',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'marquee': 'marquee 30s linear infinite',
        'marquee2': 'marquee2 30s linear infinite',
        'scan': 'scan 8s linear infinite',
        'blink': 'blink 1s step-end infinite',
        'gradient-shift': 'gradient-shift 8s ease infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px) scale(1)' },
          '50%': { transform: 'translateY(-30px) scale(1.02)' },
        },
        marquee: {
          '0%': { transform: 'translateX(0%)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        marquee2: {
          '0%': { transform: 'translateX(50%)' },
          '100%': { transform: 'translateX(0%)' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(200vh)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'gradient-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
      },
    },
  },
  plugins: [],
}

export default config
