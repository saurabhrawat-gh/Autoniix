'use server';

import { cookies } from 'next/headers';
import { locales, type Locale } from '@/i18n/config';

export async function setLocale(locale: string) {
  if (!(locales as readonly string[]).includes(locale)) return;
  const cookieStore = await cookies();
  cookieStore.set('locale', locale, {
    path: '/',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 365,
  });
}
