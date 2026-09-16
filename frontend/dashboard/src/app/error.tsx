"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/lib/ui";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("[global error]", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-surface-0">
      <div className="max-w-md w-full text-center space-y-4">
        <h1 className="text-lg font-semibold text-content-primary">Something went wrong</h1>
        <p className="text-xs text-content-tertiary">{error?.message || "An unexpected error occurred."}</p>
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button onClick={() => reset()} size="sm">
            Try again
          </Button>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-medium border border-border bg-surface-1 hover:bg-surface-2"
          >
            Home
          </Link>
        </div>
      </div>
    </div>
  );
}
