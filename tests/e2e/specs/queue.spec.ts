import { expect, test } from '../fixtures/test';

const queueStoryUrl = 'http://127.0.0.1:6006/iframe.html?id=components-queue--backend-lifecycle&viewMode=story&ssuiE2E=1';

test('loads the queue, applies websocket progress, and cancels the task', async ({
  page,
  useScenario,
  recordedRequests,
}) => {
  await useScenario('task-lifecycle');
  await page.goto(queueStoryUrl);

  await expect(page.getByRole('heading', { name: 'Mock image generation' })).toBeVisible();
  await expect(page.getByText('50%')).toBeVisible();
  await page.getByTitle('Cancel Task').click();
  await expect(page.getByText('Cancelled', { exact: true })).toBeVisible();

  await expect.poll(async () => {
    const requests = await recordedRequests();
    return requests.some(
      (item) => item.method === 'POST' && item.path === '/api/tasks/task-1/cancel',
    );
  }).toBeTruthy();
});
