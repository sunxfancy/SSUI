import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/desktop-ui',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  use: { baseURL: 'http://127.0.0.1:17421', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report/desktop', open: 'never' }]],
  projects: [{ name: 'desktop-ipc', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'yarn workspace ssui-desktop test:ipc:dev',
    url: 'http://127.0.0.1:17421', reuseExistingServer: false,
  },
});
