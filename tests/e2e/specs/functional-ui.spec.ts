import { expect, test } from '../fixtures/test';

const functionalUrl = 'http://127.0.0.1:7420/functional_ui/?path=%2Ffixtures%2Fdemo.py';

test.beforeEach(async ({ useScenario }) => {
  await useScenario('happy-path');
});

test('uploads input, prepares controls, executes, and renders the generated image', async ({
  page,
  recordedRequests,
}) => {
  await page.goto(functionalUrl);

  await expect(page.getByRole('heading', { name: 'demo.py' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '高级参数' })).toBeVisible();
  await page.getByRole('tab', { name: 'ImageUploader' }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: 'input.png',
    mimeType: 'image/png',
    buffer: Buffer.from('mock-png'),
  });
  await expect(page.getByRole('img', { name: 'preview' })).toBeVisible();

  await page.getByRole('button', { name: '运行 generate' }).click();
  const result = page.getByRole('img', { name: 'placeholder' });
  await expect(result).toBeVisible();
  await expect(result).toHaveAttribute('src', /generated\.png/);

  await expect.poll(async () => {
    const requests = await recordedRequests();
    return requests.some((item) => item.path === '/api/execute');
  }).toBeTruthy();

  const requests = await recordedRequests();
  const upload = requests.find((item) => item.path === '/files/upload');
  expect(upload).toMatchObject({
    method: 'POST',
    query: { script_path: '/fixtures/demo.py' },
    body: { filename: 'input.png', content_type: 'image/png' },
  });

  const execute = requests.find((item) => item.path === '/api/execute');
  expect(execute).toMatchObject({
    method: 'POST',
    query: { script_path: '/fixtures/demo.py', callable: 'generate' },
  });
  expect(execute.body.params.image).toEqual({
    function: 'ssui.base.Image.load',
    params: { path: '/fixtures/uploaded.png' },
  });
  expect(execute.body.details.Generation.steps).toBe(20);
});

test('shows a useful error when generation fails', async ({ page, useScenario }) => {
  await useScenario('generation-fails');
  await page.goto(functionalUrl);
  await expect(page.getByRole('button', { name: '运行 generate' })).toBeVisible();
  await page.getByRole('button', { name: '运行 generate' }).click();
  await expect(page.getByRole('alert')).toContainText('Mock generation failed');
});
