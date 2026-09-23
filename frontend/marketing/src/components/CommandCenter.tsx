"use client";

import { ArrowRight, Home, Tv, Film, Archive, Zap, Settings, Bell, Search, TrendingUp, Check } from "lucide-react";
import Button from "./ui/Button";
import Reveal from "./ui/Reveal";
import BrandMark from "./ui/BrandMark";
import { STAGES, JOBS, C } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

const NAV = [
  ["Home", Home, true],
  ["Channels", Tv],
  ["Jobs", Film],
  ["Library", Archive],
  ["Automations", Zap],
  ["Settings", Settings],
] as const;

const KPIS = [
  ["Published · 30d", "1,284", "+18%"],
  ["Avg quality", "9.4", "+0.3"],
  ["Watch hours", "412k", "+27%"],
  ["Cost / video", "$1.86", "-11%"],
];

const SPARK = [30, 42, 38, 55, 61, 58, 70, 74, 82, 79, 91, 97];

function DashboardMock() {
  return (
    <div className="window text-left">
      <div className="flex min-h-[460px]">
        {/* Sidebar */}
        <aside className="hidden md:flex flex-col w-52 shrink-0 border-r border-border bg-surface-bg/60 p-3">
          <div className="flex items-center gap-2 px-2 py-1.5 mb-3">
            <BrandMark size={20} />
            <span className="text-[13.5px] font-semibold tracking-tight text-content-primary">Autoniix</span>
            <Search className="w-3.5 h-3.5 ml-auto text-content-tertiary" />
          </div>
          <div className="card px-2.5 py-2 mb-3 flex items-center gap-2">
            <span
              className="w-5 h-5 rounded-md grid place-items-center text-[10px] font-bold text-white"
              style={{ background: C.info }}
            >
              M
            </span>
            <span className="text-[12px] text-content-primary truncate">Money Simplified</span>
          </div>
          <ul className="space-y-0.5">
            {NAV.map(([label, Icon, active]) => (
              <li
                key={label}
                className={cn(
                  "flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[12.5px]",
                  active ? "bg-surface-1 text-content-primary" : "text-content-tertiary"
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </li>
            ))}
          </ul>
          <div className="mt-auto card p-3">
            <p className="text-[10px] font-mono text-content-tertiary mb-1">Plan · Pro</p>
            <div className="h-1 rounded-full bg-surface-2 overflow-hidden">
              <div className="h-full w-[62%] bg-accent rounded-full" />
            </div>
            <p className="text-[10px] font-mono text-content-secondary mt-1.5">156 / 250 videos</p>
          </div>
        </aside>

        {/* Canvas */}
        <div className="flex-1 min-w-0 p-4 md:p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <p className="eyebrow mb-1">Overview</p>
              <h4 className="text-lg font-semibold tracking-tight text-content-primary">Good evening, Priya</h4>
            </div>
            <div className="flex items-center gap-2">
              <span className="chip bg-status-success/15 text-status-success">
                <span className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse" /> 6 running
              </span>
              <span className="w-8 h-8 rounded-full border border-border grid place-items-center text-content-tertiary">
                <Bell className="w-3.5 h-3.5" />
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
            {KPIS.map(([k, v, d]) => (
              <div key={k} className="card p-3.5 min-w-0">
                <p className="text-[10px] font-mono text-content-tertiary mb-1.5 truncate">{k}</p>
                <p className="text-xl font-bold tracking-tight text-content-primary leading-none">{v}</p>
                <span className="chip bg-status-success/15 text-status-success mt-2">
                  <TrendingUp className="w-3 h-3" /> {d}
                </span>
              </div>
            ))}
          </div>

          <div className="grid xl:grid-cols-[1.3fr_1fr] gap-3">
            {/* Chart */}
            <div className="card p-4 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-3">
                <p className="text-[12px] font-medium text-content-primary truncate">Videos published</p>
                <span className="font-mono text-[10px] text-content-tertiary whitespace-nowrap">12 wks</span>
              </div>
              <div className="h-32 flex items-end gap-1.5">
                {SPARK.map((h, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-t-sm relative overflow-hidden bg-surface-2"
                    style={{ height: `${h}%` }}
                  >
                    <div
                      className="absolute inset-0"
                      style={{ background: i === SPARK.length - 1 ? C.cream : `${C.violet}${i > 7 ? "cc" : "77"}` }}
                    />
                  </div>
                ))}
              </div>
            </div>
            {/* Recent jobs */}
            <div className="card p-4 min-w-0">
              <p className="text-[12px] font-medium text-content-primary mb-3">Active jobs</p>
              <ul className="space-y-2">
                {JOBS.slice(0, 4).map((j) => {
                  const s = STAGES[j.stage];
                  return (
                    <li key={j.title} className="flex items-center gap-2.5 text-[11.5px] min-w-0">
                      <span
                        className="w-6 h-6 rounded-md grid place-items-center shrink-0"
                        style={{ background: `${s.color}22` }}
                      >
                        {j.stage === 4 ? (
                          <Check className="w-3 h-3" style={{ color: s.color }} />
                        ) : (
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.color }} />
                        )}
                      </span>
                      <span className="text-content-primary truncate flex-1 min-w-0">{j.title}</span>
                      <span className="font-mono text-[10px] shrink-0" style={{ color: s.color }}>
                        {s.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CommandCenter() {
  return (
    <section className="section overflow-hidden">
      <div className="container-x grid lg:grid-cols-[0.9fr_1.4fr] gap-12 lg:gap-16 items-center">
        <Reveal>
          <p className="eyebrow mb-4">The command center</p>
          <h2 className="t-h1 text-content-primary">
            All your channels,
            <br />
            <span className="text-content-tertiary">one calm dashboard.</span>
          </h2>
          <p className="t-lead mt-5">
            dash.autoniix.com is where you set the rules and watch them run. Approve a script from your phone, pause a
            channel, swap a model, or just check the numbers.
          </p>
          <ul className="mt-8 space-y-3">
            {[
              "Live phase stepper for every job — research through publish",
              "Per-channel voices, styles, schedules and quality thresholds",
              "Cost, quality and retention side by side, per video",
              "Slack / email approvals with one-tap sign-off",
            ].map((t) => (
              <li key={t} className="flex items-start gap-3 text-content-secondary">
                <span className="mt-1 w-4 h-4 rounded-full bg-accent-light grid place-items-center shrink-0">
                  <Check className="w-2.5 h-2.5 text-accent" />
                </span>
                {t}
              </li>
            ))}
          </ul>
          <div className="mt-10 flex flex-wrap gap-3">
            <Button href="https://dash.autoniix.com/register" size="lg">
              Open the dashboard <ArrowRight className="w-4 h-4" />
            </Button>
            <Button href="#pricing" variant="secondary" size="lg">
              See plans
            </Button>
          </div>
        </Reveal>

        <Reveal delay={0.15} className="relative">
          <div className="absolute -inset-10 bg-brand opacity-[0.08] blur-[80px] rounded-full pointer-events-none" />
          <DashboardMock />
        </Reveal>
      </div>
    </section>
  );
}
