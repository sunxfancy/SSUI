import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import enUS from './locales/en-us.json';
import zhCN from './locales/zh-cn.json';

const locale = localStorage.getItem('locale') || 'en';

const resources = {
  "zh": {
    translation: zhCN
  },
  "en": {
    translation: enUS
  },
};


i18n
  .use(initReactI18next) // passes i18n down to react-i18next
  .init({
    resources,
    lng: locale, // language to use, more information here: https://www.i18next.com/overview/configuration-options#languages-namespaces-resources
    // you can use the i18n.changeLanguage function to change the language manually: https://www.i18next.com/overview/api#changelanguage
    // if you're using a language detector, do not define the lng option
    fallbackLng: locale,
    interpolation: {
      escapeValue: false // react already safes from xss
    },
    react: {
      useSuspense: false
    }
  });

// window.t = i18n.t.bind(i18n);
// window.i18n = i18n;

export default i18n;
