'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

interface Options<T> {
  /** Encode value to a string (return null/undefined to omit). */
  serialize?: (value: T) => string | null | undefined;
  /** Decode the URL string back to a value. */
  deserialize?: (raw: string | null) => T;
  /** Treat this value as the default and omit it from the URL. */
  defaultValue: T;
}

/**
 * Two-way bind a piece of UI state to a single URL search-param.
 * - Reads the param on mount and on history navigation.
 * - Writes via `router.replace` (no scroll, no history pollution).
 * - Falls back to default and strips the param when the value equals the default.
 */
export function useUrlState<T>(key: string, opts: Options<T>): [T, (v: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { defaultValue, serialize, deserialize } = opts;

  const decode = useCallback((raw: string | null): T => {
    if (deserialize) return deserialize(raw);
    return (raw ?? defaultValue) as unknown as T;
  }, [deserialize, defaultValue]);

  const initial = decode(searchParams?.get(key) ?? null);
  const [value, setValueState] = useState<T>(initial);

  // External URL changes (back/forward) → sync into local state
  const lastUrlValueRef = useRef<string | null>(searchParams?.get(key) ?? null);
  useEffect(() => {
    const raw = searchParams?.get(key) ?? null;
    if (raw === lastUrlValueRef.current) return;
    lastUrlValueRef.current = raw;
    setValueState(decode(raw));
  }, [searchParams, key, decode]);

  const setValue = useCallback((next: T) => {
    setValueState(next);
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(searchParams?.toString() ?? '');
    const encoded = serialize
      ? serialize(next)
      : next === defaultValue || next === undefined || next === null
        ? null
        : String(next);
    if (encoded == null || encoded === '' || encoded === serialize?.(defaultValue)) {
      params.delete(key);
    } else {
      params.set(key, encoded);
    }
    const qs = params.toString();
    lastUrlValueRef.current = encoded ?? null;
    router.replace(qs ? `${pathname}?${qs}` : pathname || '/', { scroll: false });
  }, [router, pathname, searchParams, key, serialize, defaultValue]);

  return [value, setValue];
}
