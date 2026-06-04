'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, Zap, ArrowRight } from 'lucide-react'
import GlowButton from './ui/GlowButton'

const plans = [
  {
    id: 'solo',
    name: 'Solo',
    monthly: 19,
    annual: 15,
    profiles: 1,
    videos: 20,
    seats: 1,
    popular: false,
    enterprise: false,
    features: ['1 content profile', '20 videos / month', '1 team seat', 'AI research + scripting', 'Basic analytics'],
  },
  {
    id: 'starter',
    name: 'Starter',
    monthly: 49,
    annual: 39,
    profiles: 3,
    videos: 75,
    seats: 2,
    popular: false,
    enterprise: false,
    features: ['3 content profiles', '75 videos / month', '2 team seats', 'AI research + scripting', 'Voice synthesis', 'Advanced analytics'],
  },
  {
    id: 'pro',
    name: 'Pro',
    monthly: 99,
    annual: 79,
    profiles: 10,
    videos: 250,
    seats: 5,
    popular: true,
    enterprise: false,
    features: ['10 content profiles', '250 videos / month', '5 team seats', 'All AI models', 'Priority rendering', 'Full analytics + intelligence', 'Human review workflows'],
  },
  {
    id: 'business',
    name: 'Business',
    monthly: 249,
    annual: 199,
    profiles: 30,
    videos: 750,
    seats: 15,
    popular: false,
    enterprise: false,
    features: ['30 content profiles', '750 videos / month', '15 team seats', 'All Pro features', 'Shorts + long-form pipelines', 'Dedicated support', '+$15/seat beyond 15'],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    monthly: null,
    annual: null,
    profiles: null,
    videos: null,
    seats: null,
    popular: false,
    enterprise: true,
    features: ['Unlimited profiles', 'Unlimited videos', 'Unlimited seats', 'Custom SLA', 'Dedicated infrastructure', 'Onboarding & training', 'SSO + compliance'],
  },
]

export default function Pricing() {
  const [annual, setAnnual] = useState(false)

  return (
    <section id="pricing" className="section-pad relative" style={{ overflowX: 'clip' }}>
      {/* Aurora + rainbow ambient */}
      <div className="section-glow-aurora" style={{ opacity: 0.8 }} />
      <div className="rainbow-glow" style={{ opacity: 0.4 }} />
      <div className="noise-texture" />
      <div className="section-blend section-blend-top" />
      <div className="section-blend section-blend-bottom" />
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, color-mix(in srgb, var(--accent-secondary) 28%, transparent), transparent)' }}
      />

      <div className="max-w-7xl mx-auto px-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center mb-12"
        >
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full border t-eyebrow mb-5"
            style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}
          >
            Pricing
          </div>
          <h2 className="t-display-lg mb-4" style={{ color: 'var(--text-primary)' }}>
            Simple, transparent
            <br />
            <span className="gradient-text-animated">pricing</span>
          </h2>
          <p className="t-body-lg max-w-lg mx-auto mb-8" style={{ color: 'var(--text-muted)' }}>
            Start free. Scale as you grow. No surprises.
          </p>

          {/* Toggle */}
          <div className="inline-flex items-center gap-3 glass-card rounded-xl px-2 py-1.5 border border-white/8">
            <button
              onClick={() => setAnnual(false)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                !annual ? 'bg-[#00D89F]/15 text-[#00D89F]' : 'text-white/50 hover:text-white/70'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setAnnual(true)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 ${
                annual ? 'bg-[#00D89F]/15 text-[#00D89F]' : 'text-white/50 hover:text-white/70'
              }`}
            >
              Annual
              <span className="text-xs bg-[#00D89F] text-[#0A0A0F] font-bold px-1.5 py-0.5 rounded-md">
                2 months free
              </span>
            </button>
          </div>
        </motion.div>

        {/* Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 lg:items-start">
          {plans.map((plan, i) => (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.5, delay: i * 0.07 }}
              className={`relative flex flex-col rounded-2xl p-5 border transition-all duration-300 ${
                plan.popular
                  ? 'pricing-popular bg-gradient-to-b from-[#00D89F]/8 to-transparent scale-[1.03] z-10'
                  : plan.enterprise
                  ? 'pricing-enterprise glass-card'
                  : 'glass-card hover:border-white/15'
              }`}
            >
              {/* Popular badge */}
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#00D89F] text-[#0A0A0F] text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1">
                  <Zap className="w-3 h-3 fill-[#0A0A0F]" />
                  Most Popular
                </div>
              )}

              {/* Plan name */}
              <div className="mb-4">
                <p className="t-eyebrow mb-1" style={{ color: 'var(--text-muted)' }}>{plan.name}</p>

                {/* Price */}
                <AnimatePresence mode="wait">
                  {plan.enterprise ? (
                    <div style={{ color: 'var(--text-primary)', fontSize: '1.75rem', fontWeight: 500, letterSpacing: '-0.025em', lineHeight: 1 }}>Custom</div>
                  ) : (
                    <motion.div
                      key={annual ? 'annual' : 'monthly'}
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      transition={{ duration: 0.2 }}
                      className="flex items-end gap-1"
                    >
                      <span style={{ color: 'var(--text-primary)', fontSize: '2.25rem', fontWeight: 500, letterSpacing: '-0.03em', lineHeight: 1 }}>
                        ${annual ? plan.annual : plan.monthly}
                      </span>
                      <span className="t-body-sm mb-1" style={{ color: 'var(--text-muted)' }}>/mo</span>
                    </motion.div>
                  )}
                </AnimatePresence>

                {annual && !plan.enterprise && (
                  <p className="t-micro mt-1.5" style={{ color: 'var(--accent)', textTransform: 'none', letterSpacing: 0 }}>
                    billed ${((annual ? plan.annual! : plan.monthly!) * 12)} / year
                  </p>
                )}
              </div>

              {/* Limits */}
              {!plan.enterprise && (
                <div className="flex flex-wrap gap-1.5 mb-5">
                  {[
                    `${plan.profiles} profile${plan.profiles !== 1 ? 's' : ''}`,
                    `${plan.videos} videos`,
                    `${plan.seats} seat${plan.seats !== 1 ? 's' : ''}`,
                  ].map((tag) => (
                    <span key={tag} className="text-xs bg-white/5 border border-white/8 text-white/50 px-2 py-0.5 rounded-md">
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* Features */}
              <ul className="space-y-2 flex-1 mb-6">
                {plan.features.map((feat) => (
                  <li key={feat} className="flex items-start gap-2 t-body-sm" style={{ color: 'var(--text-secondary)' }}>
                    <Check
                      className="w-3.5 h-3.5 flex-shrink-0 mt-0.5"
                      strokeWidth={1.75}
                      style={{ color: plan.enterprise ? 'var(--accent-secondary)' : 'var(--accent)' }}
                    />
                    {feat}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              {plan.enterprise ? (
                <a
                  href="mailto:hello@autoniix.com"
                  className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl border border-[#6645C1]/40 text-[#6645C1] text-sm font-semibold hover:bg-[#6645C1]/10 transition-all duration-200"
                >
                  Talk to us
                  <ArrowRight className="w-4 h-4" />
                </a>
              ) : (
                <GlowButton
                  variant={plan.popular ? 'primary' : 'ghost'}
                  size="sm"
                  className="w-full justify-center"
                  onClick={() =>
                    window.open(`https://dash.autoniix.com/register?plan=${plan.id}`, '_blank')
                  }
                >
                  {plan.id === 'solo' ? 'Start free' : 'Get started'}
                </GlowButton>
              )}
            </motion.div>
          ))}
        </div>

        {/* Fine print */}
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="text-center t-body-sm mt-8"
          style={{ color: 'var(--text-faint)' }}
        >
          Extra seats at +$15/seat/mo. All plans include AI research, scripting, voice synthesis, rendering, and analytics.
          Cancel anytime.
        </motion.p>
      </div>
    </section>
  )
}
