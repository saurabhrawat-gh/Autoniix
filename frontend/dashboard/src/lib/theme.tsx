"use client";

import { useEffect, type ReactNode } from "react";

/**
 * Autoniix ships a single dark theme (shared with autoniix.com).
 * The `dark` class is rendered on <html> in layout.tsx so Tailwind `dark:`
 * utilities and `.dark` selectors apply from the first paint; this provider
 * only guards against anything stripping the class at runtime and clears
 * stale theme keys left in localStorage by the old light/dark toggle.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    document.documentElement.classList.add("dark");
    document.documentElement.removeAttribute("data-color-theme");
    localStorage.removeItem("theme");
    localStorage.removeItem("color-theme");
  }, []);

  return <>{children}</>;
}
