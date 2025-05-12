import i18n from "i18next";
import { initReactI18next } from "react-i18next";


const resources = {
    en: {
      translation: {
        "打开已有工作空间": "Open existing workspace",
        "从预制工作流开始": "Start from preset workflow",
        "当前没有打开的目录, 您可以：": "No opened directory, you can:",
        "或者，选择我们准备的预制工作流：": "Or, choose a preset workflow:",
        "工作空间": "Workspace",
      }
    },
  };
  

i18n
  .use(initReactI18next) // passes i18n down to react-i18next
  .init({
    resources,
    lng: "cn", // language to use, more information here: https://www.i18next.com/overview/configuration-options#languages-namespaces-resources
    // you can use the i18n.changeLanguage function to change the language manually: https://www.i18next.com/overview/api#changelanguage
    // if you're using a language detector, do not define the lng option

    interpolation: {
      escapeValue: false // react already safes from xss
    }
  });

  export default i18n;
