import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { InitOptions } from 'i18next';

// Import translation files
import enTranslation from './locales/en/translation.json';
import cnTranslation from './locales/cn/translation.json';
import zhTranslation from './locales/zh/translation.json';

// Configure i18next options
const i18nOptions: InitOptions = {
  // Default language fallbacks
  fallbackLng: {
    'zh-CN': ['cn', 'zh', 'en'],
    'zh-TW': ['cn', 'zh', 'en'],
    'zh-HK': ['cn', 'zh', 'en'],
    'zh-Hant': ['cn', 'zh', 'en'],
    'zh-Hans': ['cn', 'zh', 'en'],
    'zh-SG': ['cn', 'zh', 'en'],
    'zh-MO': ['cn', 'zh', 'en'],
    'zh': ['cn', 'zh', 'en'],
    'default': ['en']
  },
  // Debug mode in development
  debug: process.env.NODE_ENV === 'development',
  // Resources containing translations
  resources: {
    en: {
      translation: enTranslation
    },
    cn: {
      translation: cnTranslation
    },
    zh: {
      translation: zhTranslation
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
