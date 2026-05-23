'use client'

import { motion } from 'framer-motion'
import AnimatedCounter from './ui/AnimatedCounter'

const STATS = [
  { value: 10,   suffix: '+',  label: 'AI models',          description: 'GPT-4o · Claude · Gemini · more',   accent: '#00D89F' },
  { value: 48,   suffix: '+',  label: 'Video components',   description: 'Remotion cinematic building blocks', accent: '#7C3AED' },
  { value: 100,  suffix: '+',  label: 'Profiles',           description: 'Any platform · any niche · any scale', accent: '#06B6D4' },
  { value: 0,    prefix: '$',  label: 'Manual effort',      description: 'End-to-end autonomous by default',   accent: '#F59E0B' },
  { value: null,               label: 'Infinite scale',     description: 'No hard cap on profiles or output',  accent: '#00D89F' },
]

export default function Stats() {
  return (
    <section className="relative py-28 overflow-hidden">
      {/* Full-bleed ambient background */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#09090F] via-[#0D0D1A] to-[#09090F]" />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(0,216,159,0.06) 0%, rgba(124,58,237,0.05) 40%, transparent 70%)',
        }}
      />

      {/* Top / bottom separator lines */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#00D89F]/15 to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#7C3AED]/10 to-transparent" />

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/8 text-xs text-white/40 font-medium tracking-[0.15em] uppercase mb-5">
            By the numbers
          </div>
          <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tighter text-white">
            Built for scale.{' '}
            <span className="gradient-text">Proven in production.</span>
          </h2>
        </motion.div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 28, scale: 0.96 }}
              whileInView={{ opacity: 1, y: 0, scale: 1 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.55, delay: i * 0.09, ease: [0.16, 1, 0.3, 1] }}
              whileHover={{ y: -4, transition: { duration: 0.2 } }}
              className="relative glass-card rounded-2xl p-6 text-center border border-white/[0.07] group overflow-hidden"
            >
              {/* Hover glow */}
              <div
                className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-400 pointer-events-none"
                style={{ background: `radial-gradient(ellipse at top, ${stat.accent}10 0%, transparent 65%)` }}
              />
              {/* Top accent line */}
              <div
                className="absolute top-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{ background: `linear-gradient(90deg, transparent, ${stat.accent}50, transparent)` }}
              />

              {/* Value */}
              {stat.value !== null ? (
                <div
                  className="text-4xl sm:text-5xl font-black tracking-tighter mb-2 font-display"
                  style={{
                    background: `linear-gradient(135deg, ${stat.accent} 0%, ${stat.accent}99 100%)`,
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  <AnimatedCounter
                    value={stat.value}
                    suffix={stat.suffix}
                    prefix={stat.prefix}
                  />
                </div>
              ) : (
                <motion.div
                  className="text-4xl sm:text-5xl font-black tracking-tighter mb-2 font-display gradient-text"
                  animate={{ scale: [1, 1.08, 1] }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                >
                  ∞
                </motion.div>
              )}

              <p className="text-white/75 text-sm font-semibold mb-1">{stat.label}</p>
              <p className="text-white/30 text-[11px] leading-snug">{stat.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
