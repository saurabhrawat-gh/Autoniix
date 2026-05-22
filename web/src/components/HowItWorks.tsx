'use client'

import { motion } from 'framer-motion'
import { Settings2, Cpu, Send } from 'lucide-react'
import GradientOrb from './ui/GradientOrb'

const steps = [
  {
    number: '01',
    icon: Settings2,
    title: 'Configure',
    description: 'Set your niche, tone, brand voice, and target platforms. Takes minutes, drives everything.',
    accent: '#00D89F',
  },
  {
    number: '02',
    icon: Cpu,
    title: 'Automate',
    description: 'AI researches trending topics, writes scripts, synthesises voice, renders video — fully autonomous.',
    accent: '#6645C1',
  },
  {
    number: '03',
    icon: Send,
    title: 'Publish',
    description: 'Content goes live on schedule. Analytics feed back into the loop. The system learns and improves.',
    accent: '#2563EB',
  },
]

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="section-pad relative overflow-hidden">
      {/* Background orb */}
      <GradientOrb
        variant="purple"
        size={800}
        className="top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ opacity: 0.12 }}
      />

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-20"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/8 text-xs text-white/40 font-medium tracking-wider uppercase mb-4">
            How it works
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black tracking-tighter text-white mb-4">
            From idea to published
            <br />
            <span className="gradient-text">in minutes</span>
          </h2>
          <p className="text-white/50 text-lg max-w-lg mx-auto">
            Three steps. Infinite content.
          </p>
        </motion.div>

        {/* Steps */}
        <div className="relative">
          {/* Connector line (desktop) */}
          <div className="hidden lg:block absolute top-16 left-[calc(16.66%+40px)] right-[calc(16.66%+40px)] h-px bg-gradient-to-r from-[#00D89F]/40 via-[#6645C1]/40 to-[#2563EB]/40 z-0" />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 lg:gap-8">
            {steps.map((step, i) => {
              const Icon = step.icon
              return (
                <motion.div
                  key={step.number}
                  initial={{ opacity: 0, y: 32 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-60px' }}
                  transition={{ duration: 0.55, delay: i * 0.15, ease: [0.16, 1, 0.3, 1] }}
                  className="flex flex-col items-center text-center relative z-10"
                >
                  {/* Step circle */}
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6 relative"
                    style={{
                      background: `linear-gradient(135deg, ${step.accent}20 0%, ${step.accent}08 100%)`,
                      border: `1px solid ${step.accent}35`,
                      boxShadow: `0 0 24px ${step.accent}20`,
                    }}
                  >
                    <Icon className="w-7 h-7" style={{ color: step.accent }} />
                    {/* Number badge */}
                    <span
                      className="absolute -top-2 -right-2 text-[10px] font-bold font-mono px-1.5 py-0.5 rounded-md"
                      style={{
                        background: step.accent,
                        color: '#0A0A0F',
                      }}
                    >
                      {step.number}
                    </span>
                  </div>

                  <h3 className="text-white font-bold text-xl mb-3 tracking-tight">
                    {step.title}
                  </h3>
                  <p className="text-white/50 text-base leading-relaxed max-w-xs">
                    {step.description}
                  </p>
                </motion.div>
              )
            })}
          </div>
        </div>

        {/* Optional human review callout */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.55, delay: 0.4 }}
          className="mt-16 flex justify-center"
        >
          <div className="glass-card rounded-2xl px-6 py-4 flex items-center gap-4 border border-white/8 max-w-xl w-full">
            <div className="w-8 h-8 rounded-lg bg-[#00D89F]/12 border border-[#00D89F]/25 flex items-center justify-center flex-shrink-0">
              <span className="text-[#00D89F] text-sm">∞</span>
            </div>
            <div>
              <p className="text-white/80 text-sm font-medium">Want manual review? Just enable it.</p>
              <p className="text-white/40 text-xs mt-0.5">Human-in-the-loop review available at every stage — approve before publish, or run fully autonomous.</p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
