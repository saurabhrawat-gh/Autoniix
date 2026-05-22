'use client'

import { motion } from 'framer-motion'
import AnimatedCounter from './ui/AnimatedCounter'

const stats = [
  { value: 10, suffix: '+', label: 'AI models orchestrated', description: 'GPT-4o, Claude, Gemini and more' },
  { value: 48, suffix: '+', label: 'Remotion components', description: 'Cinematic video building blocks' },
  { value: 100, suffix: '+', label: 'Profiles supported', description: 'Across any platform, any niche' },
  { value: 0, prefix: '$', label: 'Manual effort required', description: 'End-to-end autonomous by default' },
  { value: null, label: 'Customisable', description: 'Want manual review? Just enable it.' },
]

export default function Stats() {
  return (
    <section className="section-pad relative">
      {/* Top divider */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/8 to-transparent" />

      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-12"
        >
          <h2 className="text-2xl sm:text-3xl font-black tracking-tighter text-white">
            Built for scale. <span className="gradient-text">Proven in production.</span>
          </h2>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="glass-card rounded-2xl p-6 text-center group hover:border-[#00D89F]/20 transition-colors duration-300"
            >
              {stat.value !== null ? (
                <div className="text-3xl sm:text-4xl font-black tracking-tighter gradient-text-green mb-2">
                  <AnimatedCounter
                    value={stat.value as number}
                    suffix={stat.suffix}
                    prefix={stat.prefix}
                  />
                </div>
              ) : (
                <div className="text-3xl sm:text-4xl font-black tracking-tighter gradient-text mb-2 animate-pulse-slow">
                  ∞
                </div>
              )}
              <p className="text-white/80 text-sm font-semibold mb-1">{stat.label}</p>
              <p className="text-white/35 text-xs leading-snug">{stat.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
