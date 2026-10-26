import { test, expect, view } from './fixtures';

test('execution locks controls, displays failure and allows retry', async ({ page }) => {
  await page.route('**/api/script?*', route => route.fulfill({ json: {
    root_path: '', functions: { main: { params: {}, returns: [] } },
  } }));
  await page.route('**/api/prepare?*', route => route.fulfill({ json: {} }));
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  let calls = 0;
  await page.route('**/api/execute?*', async route => {
    calls++;
    expect(new URL(route.request().url()).searchParams.get('script_path')).toBe('测试 & #1.py');
    expect(route.request().postDataJSON()).toEqual({ params: {}, details: {} });
    if (calls === 1) await pending;
    await route.fulfill({ json: calls === 1 ? { error: 'executor unavailable' } : [] });
  });
  await page.goto(view('functional'));
  await expect(page.getByRole('button', { name: 'main', exact: true })).toBeEnabled();
  const toggle = page.getByRole('button', { name: '高级参数' });
  const initialLabel = await toggle.getAttribute('aria-expanded');
  await toggle.click();
  await expect(toggle).not.toHaveAttribute('aria-expanded', initialLabel!);
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', initialLabel!);
  await expect(page.locator('.details-empty')).toBeAttached();
  await page.getByRole('button', { name: '运行 main', exact: true }).click();
  await expect(page.getByRole('button', { name: 'main', exact: true })).toBeDisabled();
  release();
  await expect(page.getByRole('alert')).toContainText('executor unavailable');
  await page.getByRole('button', { name: '运行 main', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'main', exact: true })).toBeEnabled();
  expect(calls).toBe(2);
});

test('metadata failure is visible and cannot execute', async ({ page }) => {
  await page.route('**/api/script?*', route => route.fulfill({ status: 500, json: {} }));
  await page.goto(view('functional'));
  await expect(page.getByText('无法读取脚本信息（500）')).toBeVisible();
  await expect(page.getByRole('button', { name: '运行 main', exact: true })).toHaveCount(0);
});
