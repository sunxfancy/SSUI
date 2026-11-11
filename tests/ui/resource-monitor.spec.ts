import { test, expect, resources, view } from './fixtures';

test('resource HTTP failure keeps the current view usable and polling recovers', async ({ page }) => {
  let healthy = false;
  await page.route('**/api/resources/', route => healthy
    ? route.fulfill({ json: resources })
    : route.fulfill({ status: 503, json: { error: 'monitor temporarily unavailable' } }));
  await page.goto(view('project_settings'));
  await expect(page.getByRole('status').filter({ hasText: '资源监控连接失败' })).toBeVisible();
  await expect(page.getByLabel('主题颜色')).toBeVisible();
  healthy = true;
  await expect(page.getByLabel('机器资源')).toContainText('内存 8.0 / 16.0 GiB');
  await expect(page.getByText('资源监控连接失败')).toHaveCount(0);
});

test('disk confirmation posts the explicit decision and clears after success', async ({ page }) => {
  let pending = true;
  let decision: unknown;
  await page.route('**/api/resources/disk-requests', route => route.fulfill({ json: pending
    ? [{ id: 'test-offload', model: 'example-model', required_bytes: 4 * 2 ** 30 }]
    : [] }));
  await page.route('**/api/resources/disk-requests/test-offload', route => {
    decision = route.request().postDataJSON();
    pending = false;
    return route.fulfill({ json: decision });
  });
  await page.goto(view('project_settings'));
  const dialog = page.getByRole('dialog', { name: '磁盘 offload 确认' });
  await expect(dialog).toContainText('example-model');
  await dialog.getByRole('button', { name: '拒绝并停止' }).click();
  await expect(dialog).toHaveCount(0);
  expect(decision).toEqual({ approved: false });
  await expect(page.getByLabel('主题颜色')).toBeVisible();
});
