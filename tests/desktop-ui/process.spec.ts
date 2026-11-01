import { test, expect } from '@playwright/test';

for (const kind of ['server', 'executor']) {
  test(`${kind}: IPC failure, retry, loading lock and real status shape`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.locator('#root-path').fill('/安装 & data');
    await page.locator('#python-path').fill('/安装 & data/python');
    await page.evaluate(() => Object.assign((window as any).ipcFixture, { fail: true }));
    await page.locator(`#${kind}-start`).click();
    await expect(page.locator('#result')).toContainText('fixture permission denied');
    await page.evaluate(() => Object.assign((window as any).ipcFixture, { fail: false, delay: 300 }));
    await page.locator(`#${kind}-start`).click();
    await expect(page.locator(`#${kind}-start`)).toBeDisabled();
    await expect(page.locator(`#${kind}-restart`)).toBeDisabled();
    await expect(page.locator('#result')).toContainText('启动成功');
    const calls = await page.evaluate(() => (window as any).ipcFixture.calls);
    expect(calls.filter((call: any) => call.command === `start_${kind}`)).toHaveLength(2);
    expect(calls.at(-1)).toEqual({ command: `start_${kind}`, args: { path: '/安装 & data/python', cwd: '/安装 & data' } });
    await page.locator(`#${kind}-status`).click();
    await expect(page.locator('#result')).toContainText('正在运行中');
    await page.evaluate(() => Object.assign((window as any).ipcFixture, { running: false }));
    await page.locator(`#${kind}-status`).click();
    await expect(page.locator('#result')).toContainText('未在运行中');
    await page.locator(`#${kind}-stop`).click();
    await expect(page.locator('#result')).toContainText('已停止');
    expect(errors).toEqual([]);
  });
}
