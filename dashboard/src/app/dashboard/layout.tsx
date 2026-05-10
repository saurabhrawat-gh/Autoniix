import { type ReactNode } from 'react';
import { AppHeader } from '@/lib/components/AppHeader';
import { Sidebar } from '@/lib/components/Sidebar';
import { PageTransition } from '@/lib/components/PageTransition';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="h-screen flex overflow-hidden">
      {/* Skip to main content (keyboard a11y) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[400]
                   focus:px-3 focus:py-2 focus:rounded-md focus:bg-accent focus:text-white
                   focus:text-xs focus:font-semibold focus:outline-none focus:ring-2 focus:ring-accent/40"
      >
        Skip to main content
      </a>

      {/* Desktop sidebar */}
      <Sidebar />

      {/* Right: thin header + page content (page never scrolls; content area scrolls) */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <AppHeader />
        <div id="main-content" tabIndex={-1} className="flex-1 flex flex-col focus:outline-none overflow-y-auto overflow-x-hidden">
          <PageTransition>{children}</PageTransition>
        </div>
      </div>
    </div>
  );
}
