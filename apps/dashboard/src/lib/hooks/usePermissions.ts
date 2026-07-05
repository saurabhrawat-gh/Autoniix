'use client';

import { useState, useEffect, useCallback } from 'react';
import { authApi } from '../api-v2';

interface PermissionsState {
  permissions: string[];
  role: string;
  globalRole: string;
  loading: boolean;
  error: boolean;
}

let _cache: PermissionsState | null = null;
let _promise: Promise<void> | null = null;
const _listeners = new Set<() => void>();

function _notify() {
  _listeners.forEach(fn => fn());
}

async function _load() {
  if (_promise) return _promise;
  _promise = (async () => {
    try {
      const res = await authApi.me();
      _cache = {
        permissions: (res.data as any).permissions ?? [],
        role: res.data.role ?? 'viewer',
        globalRole: (res.data as any).global_role ?? 'user',
        loading: false,
        error: false,
      };
    } catch {
      _cache = { permissions: [], role: 'viewer', globalRole: 'user', loading: false, error: true };
    } finally {
      _notify();
    }
  })();
  return _promise;
}

export function invalidatePermissionsCache() {
  _cache = null;
  _promise = null;
  _load().catch(() => {});
}

export function hasPermission(permissions: string[], permission: string): boolean {
  return permissions.includes(permission);
}

export function usePermissions(): PermissionsState & { hasPermission: (p: string) => boolean } {
  const [state, setState] = useState<PermissionsState>(
    _cache ?? { permissions: [], role: 'viewer', globalRole: 'user', loading: true, error: false }
  );

  const sync = useCallback(() => {
    if (_cache) setState({ ..._cache });
  }, []);

  useEffect(() => {
    _listeners.add(sync);
    if (!_cache) _load().catch(() => {});
    else sync();
    return () => { _listeners.delete(sync); };
  }, [sync]);

  return {
    ...state,
    hasPermission: (p: string) => hasPermission(state.permissions, p),
  };
}
