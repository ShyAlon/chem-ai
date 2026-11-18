export const languages = {
  en: {
    name: 'English', direction: 'ltr', workspace: 'Fix-It notebook', heading: 'Start with the surface.',
    intro: 'Describe what you want to clean and which products you have on hand.',
    prompt: 'Your cleaning question', placeholder: 'What are you cleaning?', inspect: 'Review my inputs',
    example: 'Try an example', exampleText: 'How do I clean my standard-glass Apple Studio Display with water and a microfiber cloth?',
    exampleTitle: 'Studio Display · standard glass', materialTitle: 'Water and a microfiber cloth',
    scope: 'Reviewed procedure', evidence: 'Evidence', sourceLanguage: 'English source',
    emptyEvidence: 'Run a check to see the rule and source behind the decision.',
    current: 'Available in this notebook', confirm: 'Confirm these details', surface: 'Surface', material: 'Materials',
    unknown: 'Unverified', assess: 'Check procedure', working: 'Checking…', edit: 'Edit question',
    approved: 'Reviewed procedure available', unverified: 'No reviewed procedure found',
    outsideScope: 'The current notebook covers standard-glass Apple Studio Displays cleaned with water and a microfiber cloth only.',
    steps: ['Lightly dampen a clean microfiber cloth with water.', 'Wipe the standard glass with the cloth.'],
    whyTitle: 'Why it works', why: 'Water helps loosen water-soluble residue. The microfiber cloth lifts particles from the surface as you wipe.',
    rule: 'Rule', version: 'Policy version', request: 'Request ID', interpretation: 'Interpretation request', copy: 'Copy ID', copied: 'Copied',
    offline: 'You’re offline. Connect to check a procedure.', error: 'The check is temporarily unavailable. Try again.',
    language: 'App language', mismatch: 'These details are incorrect',
  },
  he: {
    name: 'עברית', direction: 'rtl', workspace: 'מחברת פתרונות', heading: 'מתחילים במשטח.',
    intro: 'תארו מה תרצו לנקות ובאילו חומרים יש לכם אפשרות להשתמש.',
    prompt: 'שאלת הניקוי שלכם', placeholder: 'מה תרצו לנקות?', inspect: 'בדיקת הפרטים',
    example: 'נסו דוגמה', exampleText: 'איך מנקים Apple Studio Display עם זכוכית רגילה, מים ומטלית מיקרופייבר?',
    exampleTitle: 'Studio Display עם זכוכית רגילה', materialTitle: 'מים ומטלית מיקרופייבר',
    scope: 'שיטה שנבדקה', evidence: 'מקורות ובדיקה', sourceLanguage: 'מקור באנגלית',
    emptyEvidence: 'לאחר הבדיקה יופיעו כאן הכלל והמקור שעליהם מבוססת התוצאה.',
    current: 'זמין במחברת', confirm: 'אישור הפרטים', surface: 'משטח', material: 'חומרים',
    unknown: 'לא אומת', assess: 'בדיקת השיטה', working: 'הבדיקה מתבצעת…', edit: 'עריכת השאלה',
    approved: 'נמצאה שיטה שנבדקה', unverified: 'לא נמצאה שיטה שנבדקה',
    outsideScope: 'המחברת מכסה כרגע רק ניקוי של Apple Studio Display עם זכוכית רגילה, במים ובמטלית מיקרופייבר.',
    steps: ['הרטיבו קלות מטלית מיקרופייבר נקייה במים.', 'נגבו את הזכוכית הרגילה במטלית.'],
    whyTitle: 'למה זה עובד', why: 'מים עוזרים לשחרר משקעים מסיסים במים. מטלית המיקרופייבר אוספת חלקיקים מפני השטח בזמן הניגוב.',
    rule: 'כלל', version: 'גרסת מדיניות', request: 'מזהה בקשה', interpretation: 'בקשת פענוח', copy: 'העתקת מזהה', copied: 'הועתק',
    offline: 'אין חיבור לרשת. התחברו כדי לבדוק שיטה.', error: 'הבדיקה אינה זמינה כרגע. נסו שוב.',
    language: 'שפת הממשק', mismatch: 'הפרטים אינם נכונים',
  },
};

export type Locale = keyof typeof languages;
export type Messages = typeof languages.en;

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
  document.documentElement.dir = languages[locale].direction;
  try {
    localStorage.setItem(key, locale);
  } catch {
    // Switching languages still works for the current session.
  }
}
