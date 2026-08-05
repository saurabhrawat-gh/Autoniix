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
      const active = res.data.find(w => w.active) ?? res.data[0];
      if (active && !active.onboarding_completed) {
        router.replace('/onboarding');
      }
    }).catch(() => {});
  }, [router]);

  return <>{children}</>;
}
