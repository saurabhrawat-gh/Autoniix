'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, isLoggedIn } from '@/lib/api-v2';

export function WorkspaceGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace('/login');
      return;
    }
    authApi.listWorkspaces().then(res => {
      if (res.data.length === 0) {
        router.replace('/onboarding');
        return;
      }
      // AE-222: Legacy seeded accounts have a real workspace row but never
      // completed onboarding (the wizard was never run for them). Force the
      // wizard for the active workspace, or — if none is marked active —
      // the first workspace the user belongs to.
      const active = res.data.find(w => w.active) ?? res.data[0];
      if (active && !active.onboarding_completed) {
        router.replace('/onboarding');
      }
    }).catch(() => {});
  }, [router]);

  return <>{children}</>;
}
