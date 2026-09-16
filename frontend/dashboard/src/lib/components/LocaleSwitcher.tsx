'use client';

import { useTranslations, useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import { Globe } from 'lucide-react';
import { locales, type Locale } from '@/i18n/config';
import { setLocale } from '@/lib/actions/locale';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  Button,
} from '@/lib/ui';
import { Check } from 'lucide-react';

export function LocaleSwitcher() {
  const t = useTranslations('locale');
  const currentLocale = useLocale();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function handleChange(locale: Locale) {
    if (locale === currentLocale) return;
    startTransition(async () => {
      await setLocale(locale);
      router.refresh();
    });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={t('label')}
          disabled={isPending}
          className="w-8 h-8 text-content-secondary hover:text-content-primary"
        >
          <Globe size={14} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[140px]">
        {locales.map((locale) => (
          <DropdownMenuItem
            key={locale}
            onSelect={() => handleChange(locale)}
            className="flex items-center justify-between gap-2"
          >
            <span>{t(locale)}</span>
            {locale === currentLocale && (
              <Check size={12} className="text-accent" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
