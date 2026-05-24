'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown } from 'lucide-react'

const faqs = [
  {
    q: 'What exactly does Autoniix do?',
    a: 'Autoniix is an end-to-end AI content automation platform. It researches trending topics, writes scripts, synthesises voice, renders video, and publishes to your platform — completely automatically. You configure it once, and it runs.',
  },
  {
    q: 'Which platforms are supported?',
    a: 'YouTube is fully supported today. Instagram, TikTok, and other platforms are on the roadmap. All content profiles are platform-agnostic by design — adding a new platform requires zero reconfiguration.',
  },
  {
    q: 'Can I review content before it publishes?',
    a: 'Absolutely. Human-in-the-loop review is available at every stage of the pipeline — after research, after scripting, after voice, or before final publish. You can run fully autonomous or require approval at any checkpoint.',
  },
  {
    q: 'What AI models does Autoniix use?',
    a: 'We use 10+ models in a hybrid stack: Gemini 2.5 Flash for research, Claude Sonnet for scriptwriting, GPT-4o for fact-checking and scene direction, GPT-4o-mini for QC, and Fish Audio for voice. All models are swappable.',
  },
  {
    q: 'How is video quality ensured?',
    a: 'Every video passes through 30+ automated quality gates covering script quality (>8.0/10 composite score), voice clarity, visual composition, thumbnail quality, and YouTube policy compliance — before it ever gets published.',
  },
  {
    q: 'How does billing work for extra seats?',
    a: 'Each plan includes a fixed number of seats. Additional seats are +$15/seat/month and can be added or removed at any time from your dashboard.',
  },
  {
    q: 'Can I cancel anytime?',
    a: 'Yes. No contracts, no lock-in. Cancel from your dashboard. For annual plans, you receive a prorated refund for unused months.',
  },
  {
    q: 'Is my content and data secure?',
    a: 'All data is encrypted in transit and at rest. We use self-hosted infrastructure (no third-party cloud for your content), with optional HashiCorp Vault secrets management for Enterprise customers.',
  },
]

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null)

  return (
    <section id="faq" className="section-pad relative">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/8 to-transparent" />

      <div className="max-w-3xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.26, ease: [0.12, 0, 0.1, 1] }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/8 text-xs text-white/40 font-medium tracking-wider uppercase mb-4">
            FAQ
          </div>
          <h2 className="text-3xl sm:text-4xl font-black tracking-tighter text-white">
            Everything you need to know
          </h2>
        </motion.div>

        <div className="space-y-2">
          {faqs.map((faq, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.26, delay: i * 0.04, ease: [0.12, 0, 0.1, 1] }}
              className="glass-card rounded-xl border border-white/8 overflow-hidden"
            >
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center justify-between px-5 py-4 text-left group"
              >
                <span className="text-white/85 font-medium text-sm pr-4 group-hover:text-white transition-colors duration-150">
                  {faq.q}
                </span>
                <motion.div
                  animate={{ rotate: open === i ? 45 : 0 }}
                  transition={{ duration: 0.12, ease: [0.16, 1, 0.3, 1] }}
                  className="flex-shrink-0 w-7 h-7 rounded-lg bg-white/5 border border-white/8 flex items-center justify-center group-hover:border-[#00D89F]/30 transition-colors duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]"
                >
                  <ChevronDown
                    className={`w-3.5 h-3.5 transition-colors duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] ${open === i ? 'text-[#00D89F]' : 'text-white/50'}`}
                  />
                </motion.div>
              </button>

              <AnimatePresence initial={false}>
                {open === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                    className="overflow-hidden"
                  >
                    <div className="px-5 pb-5 pt-1 border-t border-white/5">
                      <p className="text-white/55 text-sm leading-relaxed">{faq.a}</p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
