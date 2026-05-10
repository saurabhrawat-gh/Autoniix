'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { providersApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { Plug, ChevronRight, CheckCircle2, AlertTriangle, HelpCircle, Cpu } from '@/lib/components/Icon';

const KIND_DESC: Record<string, string> = {
  llm:    'Large language model APIs for script, research, and critique (OpenAI, Anthropic, Gemini).',
  tts:    'Text-to-speech voice synthesis (Fish Audio, ElevenLabs, Edge TTS).',
  image:  'Image generation for thumbnails and assets (DALL·E, Stability AI, placeholder).',
  search: 'Web search for research and trend data (SerpApi, Brave, mock).',
  storage:'Object storage for media files (MinIO, S3-compatible).',
};

const KIND_ICON: Record<string, string> = {
  llm: '🧠', tts: '🎙️', image: '🖼️', search: '🔍', storage: '💾',
};

export default function ProvidersIndex() {
  const [cats, setCats] = useState<any[]>([]);
  const [creds, setCreds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      providersApi.categories().then(r => setCats(r.data || [])),
      providersApi.credentials().then(r => setCreds(r.data || [])),
    ]).finally(() => setLoading(false));
  }, []);

  const grouped: Record<string, any[]> = cats.reduce((acc: any, c: any) => {
    (acc[c.kind] ||= []).push(c);
    return acc;
  }, {});

  const countHealthy = (catName: string) => {
    const myCreds = creds.filter(cr => cr.category === catName);
    const healthy = myCreds.filter(c => c.last_health_ok === true).length;
    const failing = myCreds.filter(c => c.last_health_ok === false).length;
    const total = myCreds.length;
    return { total, healthy, failing };
  };

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
          <Plug size={20} className="text-accent" /> Providers
        </h1>
        <div className="mt-2 p-3 rounded-md bg-surface-1 border border-border text-xs text-content-secondary leading-relaxed">
          <span className="font-semibold text-content-primary">Plug-in / plug-out provider chains.</span>{' '}
          Each provider category supports multiple credentials in a priority chain — the first healthy provider serves the call, with automatic fallback.
          <span className="text-content-tertiary ml-1">
            Secrets are stored in Vault/Infisical, never in your repo. Add credentials, reorder the chain, and test connectivity.
          </span>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-md border border-border bg-surface-0 p-4 animate-pulse h-28" />
          ))}
        </div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="py-20 text-center text-sm text-content-tertiary">
          <Cpu size={32} className="mx-auto mb-3 opacity-30" />
          No provider categories found. Ensure the backend is running.
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([kind, list]: any) => (
            <section key={kind}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-base">{KIND_ICON[kind] || '🔌'}</span>
                <h2 className="text-sm font-semibold text-content-primary capitalize">{kind.replace('_', ' ')}</h2>
                <p className="text-xs text-content-tertiary hidden sm:block">— {KIND_DESC[kind] || 'Provider category.'}</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {list.map((cat: any) => {
                  const { total, healthy, failing } = countHealthy(cat.name);
                  return (
                    <Link key={cat.name} href={`/dashboard/providers/${encodeURIComponent(cat.name)}`}
                      className="rounded-md border border-border bg-surface-0 p-4 hover:bg-surface-1 hover:border-accent/30 transition-all group">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="text-sm font-semibold text-content-primary group-hover:text-accent transition-colors">
                            {cat.label}
                          </div>
                          <div className="text-[10px] text-content-tertiary font-mono mt-0.5">{cat.name}</div>
                        </div>
                        <ChevronRight size={14} className="text-content-tertiary group-hover:text-accent transition-colors mt-0.5" />
                      </div>

                      <div className="mt-3 flex items-center gap-3 text-xs">
                        {total === 0 ? (
                          <span className="flex items-center gap-1 text-content-tertiary">
                            <HelpCircle size={11} /> No credentials
                          </span>
                        ) : (
                          <>
                            {healthy > 0 && (
                              <span className="flex items-center gap-1 text-emerald-500">
                                <CheckCircle2 size={11} /> {healthy} healthy
                              </span>
                            )}
                            {failing > 0 && (
                              <span className="flex items-center gap-1 text-red-500">
                                <AlertTriangle size={11} /> {failing} failing
                              </span>
                            )}
                            {total - healthy - failing > 0 && (
                              <span className="flex items-center gap-1 text-content-tertiary">
                                <HelpCircle size={11} /> {total - healthy - failing} untested
                              </span>
                            )}
                          </>
                        )}
                        <span className="ml-auto text-content-tertiary">{total} credential{total !== 1 ? 's' : ''}</span>
                      </div>

                      {/* Health bar */}
                      {total > 0 && (
                        <div className="mt-2 h-1 rounded-full bg-surface-2 overflow-hidden">
                          <div
                            className={cn('h-full rounded-full transition-all', failing > 0 ? 'bg-red-500' : 'bg-emerald-500')}
                            style={{ width: `${healthy > 0 ? (healthy / total) * 100 : failing > 0 ? 100 : 0}%` }}
                          />
                        </div>
                      )}
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
