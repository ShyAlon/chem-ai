export type Locale = 'en' | 'he';
export type Messages = Record<string, string>;

const key = 'homechem.preferences.v1';

export function initialLocale(): Locale {
  try {
    const saved = localStorage.getItem(key);
    if (saved === 'en' || saved === 'he') return saved;
  } catch {
    // Browser storage can be disabled.
  }
  return navigator.language.toLowerCase().startsWith('he') ? 'he' : 'en';
}

export function applyLocale(locale: Locale) {
  document.documentElement.lang = locale;
  document.documentElement.dir = locale === 'he' ? 'rtl' : 'ltr';
  try {
    localStorage.setItem(key, locale);
  } catch {
    // Switching languages still works for the current session.
  }
}
