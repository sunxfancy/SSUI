import React from 'react';
import type { Preview } from '@storybook/react';
import { createOfflineApi } from './mocks/api.mjs';
import { defaultRoutes } from './mocks/fixtures';
import { OfflineSocket } from './mocks/socket';
import { enableMapSet } from 'immer';
import i18n from '../desktop/src/i18n/i18n';
// 载入样式
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import "../desktop/src/App.css";

const allowLocalTestServer = () => new URLSearchParams(window.location.search).get('ssuiE2E') === '1';
const api = createOfflineApi(window.fetch.bind(window), window.location.origin, allowLocalTestServer);
enableMapSet();
window.fetch = api.fetch;
// Block business sockets, while preserving Vite's HMR connection.
const NativeWebSocket = window.WebSocket;
window.WebSocket = new Proxy(NativeWebSocket, {
  construct(Target, args) {
    const [url] = args;
    const target = new URL(url, window.location.href);
    if (allowLocalTestServer() && target.origin === 'ws://127.0.0.1:7422') {
      return Reflect.construct(Target, args);
    }
    if (target.pathname === '/ws') return new OfflineSocket(target.href);
    if (target.host !== window.location.host) {
      throw new Error(`[Storybook offline] Supply a mock service for WebSocket: ${target.pathname}`);
    }
    return Reflect.construct(Target, args);
  },
});

export const loaders: Preview['loaders'] = [
  ({ parameters }) => {
    api.configure({ ...parameters.offline, routes: { ...defaultRoutes, ...parameters.offline?.routes } });
    return {};
  },
];

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
