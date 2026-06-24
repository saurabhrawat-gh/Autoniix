import { getRequestConfig } from 'next-intl/server';
import { cookies, headers } from 'next/headers';
import { locales, defaultLocale, type Locale } from './config';

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const headersList = await headers();

  let locale: string = cookieStore.get('locale')?.value ?? '';

  if (!locale) {
    const acceptLanguage = headersList.get('accept-language') ?? 'en';
    locale = acceptLanguage.split(',')[0].split('-')[0].toLowerCase();
  }

  if (!(locales as readonly string[]).includes(locale)) {
    locale = defaultLocale;
  }

  const safeLocale = locale as Locale;

  return {
    locale: safeLocale,
    messages: (await import(`../../messages/${safeLocale}.json`)).default,
  };
});
