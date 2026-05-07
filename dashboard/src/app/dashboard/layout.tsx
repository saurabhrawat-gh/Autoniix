import { type ReactNode } from 'react';
import { AppHeader } from '@/lib/components/AppHeader';
import { PageTransition } from '@/lib/components/PageTransition';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Skip to main content (keyboard a11y) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[400]
                   focus:px-3 focus:py-2 focus:rounded-lg focus:bg-accent focus:text-white
                   focus:text-xs focus:font-semibold focus:outline-none focus:ring-2 focus:ring-accent/40"
      >
        Skip to main content
      </a>
      <AppHeader />
      {/* Skip-link target. Pages render their own <main> landmark, so use a div here. */}
      <div id="main-content" tabIndex={-1} className="flex-1 flex flex-col focus:outline-none">
        <PageTransition>{children}</PageTransition>
      </div>
    </div>
  );
}
