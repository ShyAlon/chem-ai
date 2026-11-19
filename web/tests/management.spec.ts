import { expect, test } from '@playwright/test';

test('inspects actual rules and exports a validated material addition', async ({ page }) => {
  await page.goto('/management');
  await expect(page.getByRole('heading', { name: 'Surface materials', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'ceramic', exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Resolve deterministically' }).click();
  await expect(page.locator('pre[role="status"]')).toContainText('"substrate": "ceramic"');
  await page.getByLabel('Material ID', { exact: true }).fill('copper');
  await page.getByLabel('English label', { exact: true }).fill('Copper');
  await page.getByLabel('Hebrew label', { exact: true }).fill('נחושת');
  await page.getByLabel('English aliases (one per line)', { exact: true }).fill('copper');
  await page.getByRole('button', { name: 'Add to draft', exact: true }).click();
  const draft = JSON.parse(await page.getByLabel('Edit draft JSON').inputValue());
  expect(draft.at(-1).id).toBe('copper');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Validate & export catalog' }).click();
  expect((await download).suggestedFilename()).toBe('materials.json');
  await page.getByRole('button', { name: 'עברית', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'קטלוג ואלגוריתמים' })).toBeVisible();
});
