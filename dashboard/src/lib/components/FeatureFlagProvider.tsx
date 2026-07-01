'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { flagsApi } from '@/lib/api-v2';

type FlagMap = Record<string, boolean>;

interface FeatureFlagContextValue {
  flags: FlagMap;
  isLoaded: boolean;
  reload: () => Promise<void>;
}

const FeatureFlagContext = createContext<FeatureFlagContextValue>({
  flags: {},
  isLoaded: false,
  reload: async () => {},
});

interface FeatureFlagProviderProps {
  children: ReactNode;
}

export function FeatureFlagProvider({ children }: FeatureFlagProviderProps) {
  const [flags, setFlags] = useState<FlagMap>({});
  const [isLoaded, setIsLoaded] = useState(false);
  const fetchedRef = useRef(false);

  const reload = useCallback(async () => {
    try {
      const res = await flagsApi.list();
      const map: FlagMap = {};
      for (const f of res.data ?? []) {
        map[f.key] = f.enabled;
      }
      setFlags(map);
    } catch {
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    void reload();
  }, [reload]);

  return (
    <FeatureFlagContext.Provider value={{ flags, isLoaded, reload }}>
      {children}
    </FeatureFlagContext.Provider>
  );
}

export function useFlags(): FeatureFlagContextValue {
  return useContext(FeatureFlagContext);
}

export function useFlag(key: string): boolean {
  const { flags } = useContext(FeatureFlagContext);
  return flags[key] ?? false;
}
