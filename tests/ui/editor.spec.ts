import { test, expect, view } from './fixtures';

test('Monaco keyboard save sends version and keeps edits after conflict', async ({ page }) => {
  await page.route('**/file/text?*', route => route.fulfill({ json: { content: 'original = 1', version: 'v1' } }));
  let payload: any;
  let conflict = true;
  await page.route('**/files/upload_json', async route => {
    payload = route.request().postDataJSON();
    await route.fulfill({ status: conflict ? 409 : 200, json: conflict ? { detail: 'changed' } : { success: true, version: 'v2' } });
  });
  await page.goto(view('code_editor'));
  await expect(page.locator('.code-editor-status')).toHaveText('Ready');
  const editor = page.locator('.monaco-editor textarea').first();
  await editor.focus();
  await page.keyboard.press('ControlOrMeta+a');
  await page.keyboard.insertText('local = 2');
  await expect(page.locator('.code-editor-status')).toHaveText('Unsaved changes');
  await page.keyboard.press('ControlOrMeta+s');
  await expect(page.locator('.code-editor-status')).toContainText('本地修改已保留');
  expect(payload).toEqual({ path: '测试 & #1.py', content: 'local = 2', expected_version: 'v1' });
  await expect(page.locator('.view-lines')).toContainText('local = 2');
  conflict = false;
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.locator('.code-editor-status')).toContainText('Saved at');
  await editor.focus();
  await page.keyboard.press('ControlOrMeta+s');
  await expect.poll(() => payload.expected_version).toBe('v2');
});

test('missing file disables save; view switch preserves special path', async ({ page }) => {
  await page.route('**/file/text?*', route => route.fulfill({ status: 404, json: {} }));
  await page.route('**/api/script?*', route => route.fulfill({ status: 404, json: {} }));
  await page.goto(view('code_editor'));
  await expect(page.locator('.code-editor-status')).toContainText('404');
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Functional UI', exact: true }).click();
  await expect(page.getByRole('heading', { name: '测试 & #1.py' })).toBeVisible();
  expect(new URL(page.url()).searchParams.get('path')).toBe('测试 & #1.py');
});
