"use client";

import { useState } from "react";
import { Check, ArrowRight } from "lucide-react";
import Button from "./ui/Button";
import SectionHeading from "./ui/SectionHeading";
import Reveal from "./ui/Reveal";
import { cn } from "@/lib/utils";

const PLANS = [
  {
    id: "solo",
    name: "Solo",
    monthly: 19,
    annual: 15,
    blurb: "One channel, hands off.",
    features: ["1 content profile", "20 videos / month", "1 team seat", "AI research + scripting", "Basic analytics"],
  },
  {
    id: "starter",
    name: "Starter",
    monthly: 49,
    annual: 39,
    blurb: "A small network of channels.",
    features: ["3 content profiles", "75 videos / month", "2 team seats", "Voice synthesis", "Advanced analytics"],
  },
  {
    id: "pro",
    name: "Pro",
    monthly: 99,
    annual: 79,
    popular: true,
    blurb: "Serious volume, full stack.",
    features: [
      "10 content profiles",
      "250 videos / month",
      "5 team seats",
      "All AI models",
      "Priority rendering",
      "Full analytics + intelligence",
      "Human review workflows",
    ],
  },
  {
    id: "business",
    name: "Business",
    monthly: 249,
    annual: 199,
    blurb: "Agencies and media groups.",
    features: [
      "30 content profiles",
      "750 videos / month",
      "15 team seats (+$15/seat)",
      "Everything in Pro",
      "Shorts + long-form pipelines",
      "Dedicated support",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    monthly: null,
    annual: null,
    blurb: "Your infrastructure, our engine.",
    features: [
      "Unlimited profiles, videos, seats",
      "Custom SLA",
      "Dedicated infrastructure",
      "SSO + compliance",
      "Onboarding & training",
    ],
  },
];

export default function Pricing() {
  const [annual, setAnnual] = useState(true);

  return (
    <section id="pricing" className="section scroll-mt-20">
      <div className="container-x">
        <SectionHeading
          eyebrow="Pricing"
          title={
            <>
              Priced per video,
              <br />
              <span className="text-content-tertiary">not per hour of your life.</span>
            </>
          }
          lead="Every plan includes the full pipeline. Scale up when your channels do. Cancel anytime."
        />

        <Reveal delay={0.1} className="mt-10 flex justify-center">
          <div
            role="radiogroup"
            aria-label="Billing period"
            className="inline-flex rounded-full bg-surface-0 border border-border p-1"
          >
            {[
              ["Monthly", false],
              ["Annual · save 20%", true],
            ].map(([label, val]) => (
              <button
                key={label as string}
                type="button"
                role="radio"
                aria-checked={annual === val}
                onClick={() => setAnnual(val as boolean)}
                className={cn(
                  "px-4 h-9 rounded-full text-sm transition-colors",
                  annual === val
                    ? "bg-accent-primary text-accent-primary-fg font-medium"
                    : "text-content-secondary hover:text-content-primary"
                )}
              >
                {label as string}
              </button>
            ))}
          </div>
        </Reveal>

        <div className="mt-12 grid md:grid-cols-2 xl:grid-cols-5 gap-4">
          {PLANS.map((p, i) => {
            const price = annual ? p.annual : p.monthly;
            return (
              <Reveal
                key={p.id}
                delay={0.05 * i}
                className={cn(
                  "panel card-hover p-6 flex flex-col relative",
                  p.popular && "border-accent/40 bg-surface-1 md:-translate-y-2"
                )}
              >
                {p.popular && (
                  <span className="absolute -top-3 left-6 chip bg-accent-primary text-accent-primary-fg">
                    Most popular
                  </span>
                )}
                <p className="text-sm font-semibold text-content-primary">{p.name}</p>
                <p className="text-xs text-content-tertiary mt-1 mb-5">{p.blurb}</p>
                <div className="mb-6 min-h-[52px]">
                  {price === null ? (
                    <p className="text-3xl font-bold tracking-tight text-content-primary">Custom</p>
                  ) : (
                    <p className="flex items-baseline gap-1">
                      <span className="text-4xl font-bold tracking-tighter text-content-primary">${price}</span>
                      <span className="text-xs text-content-tertiary">/ mo{annual ? ", billed yearly" : ""}</span>
                    </p>
                  )}
                </div>
                <ul className="space-y-2.5 mb-8 flex-1">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-[13px] text-content-secondary">
                      <Check
                        className="w-3.5 h-3.5 mt-0.5 shrink-0"
                        style={{ color: p.popular ? "#fcffe1" : "#5a8c3a" }}
                      />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  href={price === null ? "mailto:sales@autoniix.com" : "https://dash.autoniix.com/register"}
                  variant={p.popular ? "primary" : "secondary"}
                  className="w-full"
                >
                  {price === null ? "Talk to sales" : "Start free"} <ArrowRight className="w-4 h-4" />
                </Button>
              </Reveal>
            );
          })}
        </div>

        <p className="mt-8 text-center text-xs text-content-tertiary">
          All plans start with 20 free videos. Extra seats are $15 / seat / month. Prices in USD.
        </p>
      </div>
    </section>
  );
}
