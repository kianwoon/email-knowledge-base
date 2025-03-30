import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translation files
import enTranslation from './locales/en/translation.json';
import zhTranslation from './locales/zh/translation.json';

// Initialize i18next
i18n
  // Detect user language
  .use(LanguageDetector)
  // Pass the i18n instance to react-i18next
  .use(initReactI18next)
  // Initialize i18next
  .init({
    // Default language
    fallbackLng: 'en',
    // Debug mode in development
    debug: process.env.NODE_ENV === 'development',
    // Resources containing translations
    resources: {
      en: {
        translation: enTranslation
      },
      zh: {
        translation: zhTranslation
      }
    },
    // Detect and cache language on
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage']
    },
    // Interpolation options
    interpolation: {
      escapeValue: false // React already escapes values
    }
  });

export default i18n;
