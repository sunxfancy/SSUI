import React from 'react';
import i18n from '../src/i18n/i18n';
// 载入样式
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import "../src/App.css";

export const globalTypes = {
  locale: {
    name: 'Locale',
    description: 'Internationalization locale',
    defaultValue: 'en',
    toolbar: {
      icon: 'globe',
      items: [
        { value: 'en', right: '🇺🇸', title: 'English' },
        { value: 'zh', right: '🇨🇳', title: '中文' },
      ],
    },
  },
};

export const decorators = [
  (Story, context) => {
    i18n.changeLanguage(context.globals.locale);
    return <Story />;
  },
];
