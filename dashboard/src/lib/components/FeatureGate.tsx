import type { ReactNode } from 'react';
import { useFlag, useFlags } from '@/lib/components/FeatureFlagProvider';

interface FeatureGateProps {
  flag: string;
  fallback?: ReactNode;
  children: ReactNode;
}

export function FeatureGate({ flag, fallback = null, children }: FeatureGateProps) {
  const { isLoaded } = useFlags();
  const enabled = useFlag(flag);

  if (!isLoaded) return null;
  return enabled ? <>{children}</> : <>{fallback}</>;
}
