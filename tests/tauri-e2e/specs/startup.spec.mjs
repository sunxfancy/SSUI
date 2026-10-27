import assert from 'node:assert/strict';

describe('SSUI native shell', () => {
  it('opens the packaged webview and completes startup', async () => {
    assert.equal(await browser.getTitle(), 'SSUI');

    const root = await $('[data-testid="desktop-root"]');
    await root.waitForDisplayed({ timeout: 30_000 });

    const state = await root.getAttribute('data-app-state');
    assert.ok(['ready', 'install'].includes(state), `unexpected app state: ${state}`);
    assert.equal(await $('body').getText().then((text) => text.includes('加载中...')), false);
  });
});
