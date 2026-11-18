import { expect, test } from '@playwright/test';

test('reviews the same procedure in both languages and persists Hebrew', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Try an example' }).click();
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm these details' })).toBeVisible();
  await page.getByRole('button', { name: 'Check procedure' }).click();
  await expect(page.getByRole('heading', { name: 'Reviewed procedure available' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Clean the Studio Display' })).toHaveAttribute('href', /support\.apple\.com/);
  await expect(page.locator('.request code')).toHaveText([/^[0-9a-f]{32}$/, /^[0-9a-f]{32}$/]);

  await page.getByRole('button', { name: 'עברית' }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'he');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await page.getByRole('button', { name: 'נסו דוגמה' }).click();
  await page.getByRole('button', { name: 'בדיקת הפרטים' }).click();
  await page.getByRole('button', { name: 'בדיקת השיטה' }).click();
  await expect(page.getByRole('heading', { name: 'נמצאה שיטה שנבדקה' })).toBeVisible();
  await expect(page.getByText('studio_display_water_cleaning', { exact: true })).toBeVisible();
});

test('keeps unsupported inputs outside the reviewed procedure', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('My display has nano-texture glass.');
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByRole('heading', { name: 'No reviewed procedure found' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Check procedure' })).toHaveCount(0);
});

test('the installed shell loads offline without offering a new assessment', async ({ page, context }) => {
  await page.goto('/');
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByText('You’re offline. Connect to check a procedure.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review my inputs' })).toBeDisabled();
});
