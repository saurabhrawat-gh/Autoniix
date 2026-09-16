import { type ReactNode } from "react";
import { ChromeBar } from "@/lib/components/ChromeBar";
import { Sidebar } from "@/lib/components/Sidebar";
import { PageTransition } from "@/lib/components/PageTransition";
import { PageBreadcrumb } from "@/lib/components/PageBreadcrumb";
import { ConfirmDialogProvider } from "@/lib/components/ConfirmDialog";
import { WorkspaceGuard } from "@/lib/components/WorkspaceGuard";

/**
 * DashboardLayout — locked AppShell from §9 of DESIGN-SYSTEM-REWORK.md.
 *
 *   ┌──────────────────────────────────────────────────────┐  bg-surface-bg  (page)
 *   │  ┌────────────────────────────────────────────────┐  │
 *   │  │  ChromeBar (40px)                              │  │  bg-surface-sidebar  (shell)
 *   │  │  ┌──────────┬───────────────────────────────┐  │  │  ← continuous L
 *   │  │  │ Sidebar  │  ┌─────────────────────────┐  │  │  │
 *   │  │  │ (no bg)  │  │  Floating main card     │  │  │  │  bg-surface-0
 *   │  │  │          │  │  (rounded, hairline)    │  │  │  │
 *   │  │  └──────────┴───────────────────────────────┘  │  │
 *   │  └────────────────────────────────────────────────┘  │
 *   └──────────────────────────────────────────────────────┘
 *
 * Both the chrome bar and the sidebar are transparent so the shell's
 * surface-sidebar background paints through them as a single continuous L.
 * The main card floats with gaps on top/right/bottom + a column-gap from
 * the sidebar — those gaps reveal the shell color, completing the L.
 */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceGuard>
      <ConfirmDialogProvider>
        {/* Outer page bg — edge to edge, no padding. The chrome/sidebar reach
            the viewport edges; only the content card floats with margin. */}
        <div className="app-shell-bg h-screen w-screen overflow-hidden">
          {/* Skip-to-main (a11y) */}
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[400]
                       focus:px-3 focus:py-2 focus:rounded-md focus:bg-accent focus:text-white
                       focus:text-xs focus:font-semibold focus:outline-none focus:ring-2 focus:ring-accent/40"
          >
            Skip to main content
          </a>

          {/* Edge-to-edge shell — sidebar+chrome paint the surface-sidebar L
              all the way to the viewport edges. No outer rounding/border. */}
          <div className="h-full grid grid-rows-[40px_1fr] bg-surface-sidebar overflow-hidden">
            {/* TIER 1 — thin chrome (breadcrumb + cluster) */}
            <ChromeBar />

            {/* TIER 2 — sidebar column + floating main card.
                grid-cols [auto 1fr] lets the Sidebar's own animated width
                (motion.aside) drive the column track size. */}
            <div
              className="grid grid-cols-[auto_1fr] gap-2 pl-0 pr-3 pb-3 pt-1
                         overflow-hidden min-h-0"
            >
              <Sidebar />

              {/* Floating main content card — fully rounded, hairline border,
                  bottom margin so the sidebar bg breathes around it on three
                  sides. Soft shadow for the premium float. */}
              <main
                id="main-content"
                tabIndex={-1}
                className="bg-surface-0 rounded-lg overflow-hidden
                           border border-border/40 shadow-sm
                           focus:outline-none flex flex-col min-w-0 min-h-0"
              >
                <PageBreadcrumb />
                <div className="flex-1 overflow-y-auto overflow-x-hidden">
                  <PageTransition>{children}</PageTransition>
                </div>
              </main>
            </div>
          </div>
        </div>
      </ConfirmDialogProvider>
    </WorkspaceGuard>
  );
}
