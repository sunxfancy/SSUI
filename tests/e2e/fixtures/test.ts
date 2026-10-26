import { expect, test as base } from '@playwright/test';

const mockBaseUrl = 'http://127.0.0.1:7422';

type Fixtures = {
  useScenario: (name: string) => Promise<void>;
  recordedRequests: () => Promise<any[]>;
};

export const test = base.extend<Fixtures>({
  useScenario: async ({ request }, use) => {
    await use(async (name: string) => {
      const response = await request.put(`${mockBaseUrl}/__test__/scenario`, { data: { name } });
      expect(response.ok()).toBeTruthy();
    });
  },
  recordedRequests: async ({ request }, use) => {
    await use(async () => {
      const response = await request.get(`${mockBaseUrl}/__test__/requests`);
      expect(response.ok()).toBeTruthy();
      return (await response.json()).items;
    });
  },
});

export { expect };
