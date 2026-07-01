'use client';

import { useState, useEffect, useCallback } from 'react';
import { lookupValuesApi } from '../api-v2';

export interface LvOption {
  value: string;
  label: string;
}

const _cache = new Map<string, LvOption[]>();

export function useLookupValues(type: string, parentValue?: string): LvOption[] {
  const key = `${type}:${parentValue ?? ''}`;
  const [opts, setOpts] = useState<LvOption[]>(_cache.get(key) ?? []);

  const load = useCallback(async () => {
    try {
      const res = await lookupValuesApi.list(type, parentValue || undefined);
      const mapped: LvOption[] = (res.data ?? []).map((r: any) => ({
        value: r.value,
        label: r.label,
      }));
      _cache.set(key, mapped);
      setOpts(mapped);
    } catch { /* non-fatal — dropdowns fall back to empty */ }
  }, [type, parentValue, key]);

  useEffect(() => {
    if (!_cache.has(key)) load();
  }, [key, load]);

  return opts;
}
