import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '../fixtures/test';

test('Functional UI has no serious or critical accessibility violations', async ({ page, useScenario }) => {
  await useScenario('happy-path');
  await page.goto('http://127.0.0.1:7420/functional_ui/?path=%2Ffixtures%2Fdemo.py');
  await expect(page.getByRole('heading', { name: 'demo.py' })).toBeVisible();

  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter(
    violation => violation.impact === 'serious' || violation.impact === 'critical',
  );
  expect(blocking).toEqual([]);
});
