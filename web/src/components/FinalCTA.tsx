'use client'

import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import GlowButton from './ui/GlowButton'
import GradientOrb from './ui/GradientOrb'

export default function FinalCTA() {
  return (
    <section className="relative py-32 overflow-hidden">
      {/* Glowing orbs */}
      <GradientOrb
        variant="green"
        size={600}
        className="top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ opacity: 0.25 }}
      />
      <GradientOrb
        variant="purple"
        size={400}
        className="top-1/2 left-[30%] -translate-y-1/2"
        style={{ opacity: 0.15 }}
      />

      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/8 to-transparent" />

      <div className="max-w-4xl mx-auto px-6 text-center relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00D89F]/25 bg-[#00D89F]/8 text-sm text-[#00D89F] font-medium mb-8">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00D89F] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00D89F]" />
            </span>
            Free to start. No credit card required.
          </div>

          <h2 className="font-display text-4xl sm:text-5xl md:text-6xl font-black tracking-tighter text-white mb-6 leading-tight">
            Your first automated
            <br />
            <span className="gradient-text-animated font-serif-display">content channel</span>
            <br />
            is one click away.
          </h2>

          <p className="text-white/50 text-xl mb-10 max-w-xl mx-auto leading-relaxed">
            Join creators building content empires on autopilot.
            Set it up once. Let it run forever.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <GlowButton
              size="lg"
              onClick={() => window.open('https://dash.autoniix.com/register', '_blank')}
              className="flex items-center gap-2 text-lg px-10 py-5"
            >
              Start automating free
              <ArrowRight className="w-5 h-5" />
            </GlowButton>
          </div>

          <p className="text-white/25 text-sm mt-6">
            No credit card required · Cancel anytime · Setup in minutes
          </p>
        </motion.div>
      </div>
    </section>
  )
}
