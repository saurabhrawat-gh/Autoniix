"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import GlowButton from "./ui/GlowButton";
import GradientOrb from "./ui/GradientOrb";

export default function FinalCTA() {
  return (
    <section className="relative py-32" style={{ overflowX: "clip" }}>
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

      {/* Aurora + rainbow glow combo */}
      <div className="section-glow-aurora" style={{ opacity: 1 }} />
      <div className="rainbow-glow" style={{ opacity: 0.7 }} />
      <div className="noise-texture" />
      <div className="section-blend section-blend-top" />

      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, color-mix(in srgb, var(--accent) 30%, transparent), transparent)",
        }}
      />

      <div className="max-w-4xl mx-auto px-6 text-center relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Badge */}
          <div
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border t-eyebrow mb-8"
            style={{
              borderColor: "color-mix(in srgb, var(--accent) 28%, transparent)",
              background: "color-mix(in srgb, var(--accent) 8%, transparent)",
              color: "var(--accent)",
              letterSpacing: "0.18em",
            }}
          >
            <span className="relative flex h-2 w-2">
              <span
                className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                style={{ background: "var(--accent)" }}
              />
              <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: "var(--accent)" }} />
            </span>
            Free to start. No credit card required.
          </div>

          <h2 className="t-display-xl mb-6" style={{ color: "var(--text-primary)" }}>
            Your first automated
            <br />
            <span className="gradient-shimmer">content channel</span>
            <br />
            is one click away.
          </h2>

          <p className="t-body-lg mb-10 max-w-xl mx-auto" style={{ color: "var(--text-muted)" }}>
            Join creators building content empires on autopilot. Set it up once. Let it run forever.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <GlowButton
              size="lg"
              onClick={() => window.open("https://dash.autoniix.com/register", "_blank")}
              className="flex items-center gap-2 text-lg px-10 py-5"
            >
              Start automating free
              <ArrowRight className="w-5 h-5" />
            </GlowButton>
          </div>

          <p className="t-body-sm mt-6" style={{ color: "var(--text-faint)" }}>
            No credit card required · Cancel anytime · Setup in minutes
          </p>
        </motion.div>
      </div>
    </section>
  );
}
