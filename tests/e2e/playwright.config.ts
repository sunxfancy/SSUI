import { defineConfig, devices } from '@playwright/test';

const isCI = Boolean(process.env.CI);
const repoRoot = process.cwd();
const crossBrowser = process.env.SSUI_E2E_CROSS_BROWSER === '1';

export default defineConfig({
  testDir: './specs',
  fullyParallel: false,
  // The scenario-driven mock is intentionally a single deterministic state machine.
  workers: 1,
  retries: isCI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  reporter: isCI ? [['line'], ['html', { outputFolder: 'test-results/html', open: 'never' }]] : 'list',
  outputDir: 'test-results/artifacts',
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    ...(crossBrowser ? [
      { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
      { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    ] : []),
  ],
  webServer: [
    {
      command: 'node dependencies/venv.cjs python -m tests.mock_api',
      cwd: repoRoot,
      url: 'http://127.0.0.1:7422/',
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
    {
      command: 'yarn workspace ssui-functional_ui dev --host 127.0.0.1',
      cwd: repoRoot,
      url: 'http://127.0.0.1:7420/functional_ui/',
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
    {
      command: 'yarn workspace ssui-desktop storybook --host 127.0.0.1 --ci',
      cwd: repoRoot,
      url: 'http://127.0.0.1:6006/',
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
  ],
});
