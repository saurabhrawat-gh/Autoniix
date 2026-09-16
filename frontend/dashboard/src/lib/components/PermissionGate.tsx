'use client';

import type { ReactNode } from 'react';
import { usePermissions } from '../hooks/usePermissions';

interface Props {
  permission: string;
  fallback?: ReactNode;
  children: ReactNode;
}

/**
 * Renders children only when the authenticated user holds `permission`.
 * Renders `fallback` (default: null) while loading or when denied.
 */
export function PermissionGate({ permission, fallback = null, children }: Props) {
  const { hasPermission, loading } = usePermissions();
  if (loading) return null;
  if (!hasPermission(permission)) return <>{fallback}</>;
  return <>{children}</>;
}
