import { test as base, expect } from '@playwright/test';

export const defaults = {
  theme: 'light', auto_open_details: false,
  external_code_editor: '', civitai_token: '',
};

// Real application/React/Monaco; only the service boundary is simulated.
// Unexpected API calls fail the test, so fixtures cannot silently hide regressions.
export const test = base.extend<{ serviceGuard: void }>({
  serviceGuard: [async ({ page }, use) => {
    const unexpected: string[] = [];
    const states = new Map<string, unknown>();
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route(url => /^\/(api|config|file|files|extension)\//.test(url.pathname), async route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/api/ui_state_load' || path === '/api/ui_state_store') {
        const url = new URL(route.request().url());
        const key = JSON.stringify([url.searchParams.get('script_path'), url.searchParams.get('view')]);
        if (route.request().method() === 'POST') {
          states.set(key, route.request().postDataJSON().state_data);
          return route.fulfill({ json: { success: true } });
        }
        return route.fulfill({ json: states.get(key) ?? {} });
      }
      if (path === '/config/') return route.fulfill({ json: { ui: defaults } });
      unexpected.push(`${route.request().method()} ${path}`);
      await route.fulfill({ status: 501, json: { error: 'Unmocked API' } });
    });
    await use();
    expect(unexpected, 'Unexpected service calls').toEqual([]);
    expect(errors, 'Uncaught browser errors').toEqual([]);
  }, { auto: true }],
});
export { expect };
export const view = (name: string, path = '测试 & #1.py') =>
  `/functional_ui/?${new URLSearchParams({ view: name, path })}`;
