import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { InitOptions } from 'i18next';

// Import translation files
import enTranslation from './locales/en/translation.json';
import cnTranslation from './locales/cn/translation.json';

// Configure i18next options
const i18nOptions: InitOptions = {
  // Default language fallbacks - ensure all Chinese variants map to 'cn'
  fallbackLng: {
    'zh-CN': ['cn', 'en'],
    'zh-TW': ['cn', 'en'],
    'zh-HK': ['cn', 'en'],
    'zh-Hant': ['cn', 'en'],
    'zh-Hans': ['cn', 'en'],
    'zh-SG': ['cn', 'en'],
    'zh-MO': ['cn', 'en'],
    'zh': ['cn', 'en'],
    'default': ['en']
  },
  // Debug mode in development
  debug: process.env.NODE_ENV === 'development',
  // Resources containing translations - only 'en' and 'cn'
  resources: {
    en: {
      translation: enTranslation
    },
    cn: {
      translation: cnTranslation
    }
  },
  // Detect and cache language on
  detection: {
    order: ['querystring', 'localStorage', 'navigator', 'htmlTag'],
    lookupQuerystring: 'lng',
    lookupLocalStorage: 'i18nextLng',
    caches: ['localStorage']
  },
  // Interpolation options
  interpolation: {
    escapeValue: false // React already escapes values
  }
};

// Initialize i18next
i18n
  // Detect user language
  .use(LanguageDetector)
  // Pass the i18n instance to react-i18next
  .use(initReactI18next)
  // Initialize i18next
  .init(i18nOptions);

// Handle language detection - default Chinese variants to 'cn'
const originalLanguageDetector = i18n.services.languageDetector;
if (originalLanguageDetector) {
  const originalDetect = originalLanguageDetector.detect;
  originalLanguageDetector.detect = () => {
    const detectedLanguage = originalDetect.call(originalLanguageDetector);
    // If it's any Chinese variant, return 'cn'
    if (typeof detectedLanguage === 'string' && detectedLanguage.startsWith('zh')) {
      return 'cn';
    }
    return detectedLanguage;
  };
}

export default i18n;
