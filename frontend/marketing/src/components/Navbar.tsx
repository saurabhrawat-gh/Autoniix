"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, ArrowRight } from "lucide-react";
import Button from "./ui/Button";
import BrandMark from "./ui/BrandMark";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { label: "Product", href: "#product" },
  { label: "Pipeline", href: "#pipeline" },
  { label: "Features", href: "#features" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 16);
    handler();
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return (
    <header className="fixed top-0 inset-x-0 z-50 pt-3 px-3 md:pt-4 md:px-6 pointer-events-none">
      <nav
        className={cn(
          "container-x pointer-events-auto flex items-center justify-between h-14 rounded-2xl border transition-all duration-300",
          scrolled || open
            ? "bg-surface-0/85 backdrop-blur-xl border-border shadow-elevated"
            : "bg-transparent border-transparent"
        )}
      >
        <a href="/" className="flex items-center gap-2.5 group">
          <BrandMark size={24} />
          <span className="text-[15px] font-semibold tracking-tight text-content-primary">Autoniix</span>
        </a>

        <div className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="px-3.5 py-2 rounded-full text-sm text-content-secondary hover:text-content-primary hover:bg-surface-2 transition-colors"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-2">
          <Button href="https://dash.autoniix.com/login" variant="ghost">
            Sign in
          </Button>
          <Button href="https://dash.autoniix.com/register">
            Start free <ArrowRight className="w-4 h-4" />
          </Button>
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="md:hidden btn btn-ghost w-10 h-10 p-0"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="md:hidden pointer-events-auto mt-2 panel p-3 flex flex-col gap-1 bg-surface-0/95 backdrop-blur-xl"
          >
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="px-4 py-3 rounded-xl text-[15px] text-content-secondary hover:text-content-primary hover:bg-surface-2"
              >
                {l.label}
              </a>
            ))}
            <div className="hairline my-2" />
            <div className="grid grid-cols-2 gap-2 p-1">
              <Button href="https://dash.autoniix.com/login" variant="secondary">
                Sign in
              </Button>
              <Button href="https://dash.autoniix.com/register">Start free</Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
