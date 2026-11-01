import { test, expect, defaults, view } from './fixtures';

test('settings persist theme, checkbox and text across reload', async ({ page }) => {
  let config = { ...defaults };
  await page.route('**/config/', async route => {
    if (route.request().method() === 'POST') {
      config = { ...config, ...route.request().postDataJSON().ui };
    }
    await route.fulfill({ json: { ui: config } });
  });
  await page.goto(view('project_settings'));
  await expect(page.getByLabel('主题颜色')).toHaveValue('light');
  await page.getByLabel('主题颜色').selectOption('dark');
  await page.getByLabel('自动打开详细面板').check();
  await page.getByLabel('外部代码编辑器', { exact: true }).fill('code --wait');
  await expect(page.locator('.save-status')).toHaveText('所有更改已保存');
  expect(config).toMatchObject({ theme: 'dark', auto_open_details: true, external_code_editor: 'code --wait' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.getByLabel('外部代码编辑器', { exact: true })).toHaveValue('code --wait');
  await expect(page.getByLabel('自动打开详细面板')).toBeChecked();
  await page.getByRole('button', { name: '恢复默认值' }).click();
  await expect(page.getByLabel('主题颜色')).toHaveValue('system');
  await expect(page.getByLabel('外部代码编辑器', { exact: true })).toHaveValue('');
  await expect(page.locator('.save-status')).toHaveText('所有更改已保存');
});

test('failed autosave retains edits and explicit retry saves them', async ({ page }) => {
  let fail = true;
  let saved: unknown;
  await page.route('**/config/', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { ui: defaults } });
    saved = route.request().postDataJSON();
    await route.fulfill({ status: fail ? 503 : 200, json: fail ? { error: 'offline' } : { message: 'Config updated' } });
  });
  await page.goto(view('project_settings'));
  await expect(page.getByLabel('主题颜色')).toHaveValue('light');
  const editor = page.getByLabel('外部代码编辑器', { exact: true });
  await editor.fill('my editor');
  await expect(page.getByRole('alert')).toContainText('503');
  await expect(editor).toHaveValue('my editor');
  await expect(page.locator('.save-status')).toHaveText('保存失败');
  fail = false;
  await page.getByRole('button', { name: '重试保存' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('.save-status')).toHaveText('所有更改已保存');
  expect(saved).toEqual({ ui: { external_code_editor: 'my editor' } });
});
