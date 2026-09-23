"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus } from "lucide-react";
import SectionHeading from "./ui/SectionHeading";
import Reveal from "./ui/Reveal";
import { cn } from "@/lib/utils";

const FAQS = [
  {
    q: "What exactly does Autoniix do?",
    a: "Autoniix is an end-to-end AI video generation and automation platform. It researches trending topics, writes scripts, synthesises voice, renders video, and publishes to YouTube — completely automatically. You configure it once, and it runs.",
  },
  {
    q: "Which platforms are supported?",
    a: "Autoniix v1 is built exclusively for YouTube — both Shorts and long-form. Research, scripts, voice, rendering, thumbnails and uploads are all tuned for YouTube quality and policy. Other platforms may be added in future releases.",
  },
  {
    q: "Can I review content before it publishes?",
    a: "Yes. Human-in-the-loop review is available at every stage — after research, after scripting, after voice, or before final publish. Run fully autonomous or require approval at any checkpoint.",
  },
  {
    q: "What AI models does Autoniix use?",
    a: "A hybrid stack of 10+ models: Gemini 2.5 Flash for research, Claude Sonnet for scriptwriting, GPT-4o for fact-checking and scene direction, GPT-4o mini for QC, and Fish Audio for voice. All models are swappable.",
  },
  {
    q: "How is video quality ensured?",
    a: "Every video passes 30+ automated quality gates covering script quality (≥ 8.0 / 10 composite), voice clarity, visual composition, thumbnail quality and YouTube policy compliance — before it is ever published.",
  },
  {
    q: "How does billing work for extra seats?",
    a: "Each plan includes a fixed number of seats. Additional seats are $15 / seat / month and can be added or removed at any time from your dashboard.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. No contracts, no lock-in. Cancel from your dashboard. Annual plans receive a prorated refund for unused months.",
  },
  {
    q: "Is my content and data secure?",
    a: "All data is encrypted in transit and at rest on self-hosted infrastructure, with optional HashiCorp Vault secrets management for Enterprise customers.",
  },
];

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section id="faq" className="section scroll-mt-20">
      <div className="container-x grid lg:grid-cols-[0.8fr_1.2fr] gap-12">
        <SectionHeading
          align="left"
          eyebrow="FAQ"
          title={
            <>
              Questions,
              <br />
              <span className="text-content-tertiary">answered.</span>
            </>
          }
          lead={
            <>
              Something else?{" "}
              <a href="mailto:hello@autoniix.com" className="text-accent underline underline-offset-4">
                hello@autoniix.com
              </a>
            </>
          }
        />

        <Reveal delay={0.1} className="panel divide-y divide-border">
          {FAQS.map((f, i) => {
            const isOpen = open === i;
            return (
              <div key={f.q}>
                <button
                  type="button"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                  className="w-full flex items-center justify-between gap-6 px-6 py-5 text-left hover:bg-surface-1/60 transition-colors"
                >
                  <span
                    className={cn(
                      "text-[15px] font-medium",
                      isOpen ? "text-content-primary" : "text-content-secondary"
                    )}
                  >
                    {f.q}
                  </span>
                  <Plus
                    className={cn(
                      "w-4 h-4 shrink-0 text-content-tertiary transition-transform duration-300",
                      isOpen && "rotate-45"
                    )}
                  />
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                      className="overflow-hidden"
                    >
                      <p className="px-6 pb-6 text-sm text-content-secondary leading-relaxed">{f.a}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </Reveal>
      </div>
    </section>
  );
}
