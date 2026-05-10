'use client';

import { createContext, useContext, useEffect, useState, useCallback, useRef, type ReactNode } from 'react';
import { api, wsEvents, isLoggedIn } from '../api';

type EnvMode = 'test' | 'production';
export type WsStatus = 'connecting' | 'live' | 'offline';
export type Density = 'comfortable' | 'compact';

export interface NotificationItem {
  id: string;
  title: string;
  body?: string;
  variant: 'info' | 'success' | 'error' | 'warning';
  createdAt: number;
  href?: string;
  read?: boolean;
}

interface AppState {
  envMode: EnvMode;
  envSwitching: boolean;
  systemStopped: boolean;
  channelCount: number;
  wsStatus: WsStatus;
  density: Density;
  setDensity: (d: Density) => void;
  notifications: NotificationItem[];
  pushNotification: (n: Omit<NotificationItem, 'id' | 'createdAt' | 'read'>) => void;
  markAllNotificationsRead: () => void;
  clearNotifications: () => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  refresh: () => Promise<void>;
  switchEnv: (mode: EnvMode, confirm?: boolean) => Promise<void>;
  setSystemStopped: (v: boolean) => void;
}

const noop = () => {};
const Ctx = createContext<AppState>({
  envMode: 'test',
  envSwitching: false,
  systemStopped: false,
  channelCount: 0,
  wsStatus: 'connecting',
  density: 'comfortable',
  setDensity: noop,
  notifications: [],
  pushNotification: noop,
  markAllNotificationsRead: noop,
  clearNotifications: noop,
  paletteOpen: false,
  setPaletteOpen: noop,
  refresh: async () => {},
  switchEnv: async () => {},
  setSystemStopped: noop,
});

const NOTIF_KEY = 'dashboard_notifications_v1';
const DENSITY_KEY = 'dashboard_density_v1';
const MAX_NOTIFICATIONS = 50;

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [envMode, setEnvMode] = useState<EnvMode>('test');
  const [envSwitching, setEnvSwitching] = useState(false);
  const [systemStopped, setSystemStopped] = useState(false);
  const [channelCount, setChannelCount] = useState(0);
  const [wsStatus, setWsStatus] = useState<WsStatus>('connecting');
  const [density, setDensityState] = useState<Density>('comfortable');
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (typeof window === 'undefined') return;
    if (!localStorage.getItem('dashboard_token')) return;
    try {
      const [env, stats] = await Promise.all([
        api.environment().catch(() => null),
        api.stats().catch(() => null),
      ]);
      if (env?.data?.mode) setEnvMode(env.data.mode);
      else if (env?.mode) setEnvMode(env.mode);
      const s = stats?.data ?? stats;
      if (s) {
        setSystemStopped(!!s.emergency_stop);
        setChannelCount(s?.channels?.total ?? 0);
      }
    } catch {
      // best-effort
    }
  }, []);

  const switchEnv = useCallback(async (mode: EnvMode, confirm = false) => {
    setEnvSwitching(true);
    try {
      await api.switchEnvironment(mode, confirm);
      setEnvMode(mode);
    } finally {
      setEnvSwitching(false);
    }
  }, []);

  // Persist density + load notifications from localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const d = localStorage.getItem(DENSITY_KEY);
      if (d === 'compact' || d === 'comfortable') setDensityState(d);
      const n = localStorage.getItem(NOTIF_KEY);
      if (n) setNotifications(JSON.parse(n).slice(0, MAX_NOTIFICATIONS));
    } catch {}
  }, []);

  // Apply density attribute on <html> for CSS hooks
  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.setAttribute('data-density', density);
    try { localStorage.setItem(DENSITY_KEY, density); } catch {}
  }, [density]);

  const setDensity = useCallback((d: Density) => setDensityState(d), []);

  const pushNotification = useCallback((n: Omit<NotificationItem, 'id' | 'createdAt' | 'read'>) => {
    setNotifications(prev => {
      const next: NotificationItem[] = [
        { ...n, id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, createdAt: Date.now(), read: false },
        ...prev,
      ].slice(0, MAX_NOTIFICATIONS);
      try { localStorage.setItem(NOTIF_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const markAllNotificationsRead = useCallback(() => {
    setNotifications(prev => {
      const next = prev.map(n => ({ ...n, read: true }));
      try { localStorage.setItem(NOTIF_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
    try { localStorage.removeItem(NOTIF_KEY); } catch {}
  }, []);

  // Periodic stats refresh
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15000);
    return () => clearInterval(t);
  }, [refresh]);

  // Single shared WebSocket connection for all consumers
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    if (typeof window === 'undefined' || !isLoggedIn()) return;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    let connectTimeout: ReturnType<typeof setTimeout> | null = null;
    function connect() {
      if (stopped) return;
      setWsStatus('connecting');
      try {
        const ws = wsEvents();
        wsRef.current = ws;
        // If the socket doesn't open within 5s, treat as offline
        connectTimeout = setTimeout(() => {
          if (ws.readyState !== WebSocket.OPEN) {
            setWsStatus('offline');
            try { ws.close(); } catch {}
          }
        }, 5000);
        ws.onopen = () => {
          if (connectTimeout) { clearTimeout(connectTimeout); connectTimeout = null; }
          setWsStatus('live');
        };
        ws.onclose = () => {
          if (connectTimeout) { clearTimeout(connectTimeout); connectTimeout = null; }
          if (stopped) return;
          setWsStatus('offline');
          reconnectTimer = setTimeout(connect, 5000);
        };
        ws.onerror = () => {
          try { ws.close(); } catch {}
        };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            // Surface job lifecycle events as notifications
            if (msg.type === 'job_update' && msg.data) {
              const { status, title, content_id } = msg.data;
              if (status === 'failed') {
                pushNotification({
                  title: 'Job failed',
                  body: title || content_id,
                  variant: 'error',
                  href: content_id ? `/dashboard/jobs/${content_id}` : undefined,
                });
              } else if (status === 'delivered' || status === 'test_delivered') {
                pushNotification({
                  title: 'Video delivered',
                  body: title || content_id,
                  variant: 'success',
                  href: content_id ? `/dashboard/jobs/${content_id}` : undefined,
                });
              }
            }
          } catch {}
        };
      } catch {
        setWsStatus('offline');
        reconnectTimer = setTimeout(connect, 5000);
      }
    }
    connect();
    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (connectTimeout) clearTimeout(connectTimeout);
      try { wsRef.current?.close(); } catch {}
    };
  }, [pushNotification]);

  return (
    <Ctx.Provider value={{
      envMode, envSwitching, systemStopped, channelCount, wsStatus,
      density, setDensity,
      notifications, pushNotification, markAllNotificationsRead, clearNotifications,
      paletteOpen, setPaletteOpen,
      refresh, switchEnv, setSystemStopped,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAppState() {
  return useContext(Ctx);
}
