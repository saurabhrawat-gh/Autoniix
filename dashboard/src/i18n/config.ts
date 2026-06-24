export const locales = ['en', 'ja', 'hi', 'es'] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = 'en';

export const localeLabels: Record<Locale, string> = {
  en: 'English',
  ja: '日本語',
  hi: 'हिन्दी',
  es: 'Español',
};

export const rtlLocales: Locale[] = [];
