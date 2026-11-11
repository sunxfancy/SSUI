import { defineConfig } from '@playwright/test';
export default defineConfig({
    testDir: './tests/mcp-ui', workers: 1, timeout: 60000,
    use: { baseURL: 'http://127.0.0.1:17424', channel: process.env.SSUI_TEST_BROWSER_CHANNEL, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
    outputDir: 'build/mcp-ui-results',
    webServer: { command: 'yarn test:mcp:server', url: 'http://127.0.0.1:17424/test/files', reuseExistingServer: false, timeout: 30000 },
});
