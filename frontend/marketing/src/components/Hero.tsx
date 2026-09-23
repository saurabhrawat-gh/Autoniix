"use client";

import { motion } from "framer-motion";
import { ArrowRight, PlayCircle } from "lucide-react";
import Button from "./ui/Button";
import StudioMockup from "./StudioMockup";

const EASE = [0.16, 1, 0.3, 1] as const;
const rise = (delay: number) => ({
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.7, delay, ease: EASE },
});

export default function Hero() {
  return (
    <section className="relative pt-36 md:pt-44 pb-16 md:pb-24 overflow-hidden" id="top">
      <div className="absolute inset-0 hero-spot pointer-events-none" />
      <div className="absolute inset-x-0 top-0 h-[70vh] grid-bg pointer-events-none" />

      <div className="container-x relative z-10 text-center">
        <motion.div {...rise(0.05)} className="flex justify-center mb-7">
          <span className="pill">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-success opacity-70" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-status-success" />
            </span>
            Autoniix v2.5 — now with Shorts + long-form pipelines
          </span>
        </motion.div>

        <motion.h1 {...rise(0.15)} className="t-display text-cream mx-auto max-w-5xl">
          AI that makes the video.
          <br className="hidden sm:block" />
          <span className="text-content-tertiary"> You keep the channel.</span>
        </motion.h1>

        <motion.p {...rise(0.28)} className="t-lead mx-auto mt-7 max-w-2xl">
          Autoniix researches trends, writes the script, voices it, renders every frame and publishes to YouTube — on a
          schedule you set once. One channel or a hundred.
        </motion.p>

        <motion.div {...rise(0.38)} className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button href="https://dash.autoniix.com/register" size="lg" className="min-w-[200px]">
            Start automating free <ArrowRight className="w-4 h-4" />
          </Button>
          <Button href="#product" variant="secondary" size="lg" className="min-w-[180px]">
            <PlayCircle className="w-4 h-4" /> Watch it run
          </Button>
        </motion.div>

        <motion.p {...rise(0.48)} className="mt-5 font-mono text-[11px] text-content-tertiary tracking-wide">
          No credit card · 20 videos free · Cancel anytime
        </motion.p>
      </div>

      {/* Product mock */}
      <motion.div
        id="product"
        initial={{ opacity: 0, y: 56, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 1, delay: 0.55, ease: EASE }}
        className="container-x relative z-10 mt-16 md:mt-24 scroll-mt-32"
      >
        <div className="absolute -inset-x-6 -top-24 h-64 bg-brand opacity-[0.12] blur-[90px] rounded-full pointer-events-none" />
        <StudioMockup />
        <p className="mt-4 text-center font-mono text-[11px] text-content-tertiary">
          Live view of a real pipeline run — research → script → voice → render → publish
        </p>
      </motion.div>
    </section>
  );
}
