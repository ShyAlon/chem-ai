import { expect, test } from '@playwright/test';

test('a chemical-treated drain does not offer plunging instructions', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('How do I unclog my sink after using drain cleaner?');
  await page.getByRole('button', { name: 'Review my inputs', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No reviewed procedure found', exact: true })).toBeVisible();
  await expect(page.getByText(/do not plunge or add products/)).toBeVisible();
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Confirm conditions and show unclogging steps', exact: true })).toHaveCount(0);
});

test('Hebrew unclogging uses the English resolver and requires all conditions', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'עברית', exact: true }).click();
  await page.getByRole('textbox').fill('איך פותחים סתימה בכיור?');
  const interpreted = page.waitForResponse(item => item.url().endsWith('/api/interpret') && item.request().method() === 'POST');
  await page.getByRole('button', { name: 'בדיקת הפרטים', exact: true }).click();
  expect(await (await interpreted).json()).toMatchObject({ intent: 'unclog', surface: 'sink_drain', translated_text: 'How do I unclog my sink?' });
  const approve = page.getByRole('button', { name: 'אישור התנאים והצגת שלבי פתיחת הסתימה', exact: true });
  await expect(approve).toBeDisabled();
  const conditions = page.getByRole('checkbox');
  await expect(conditions).toHaveCount(3);
  await conditions.nth(0).check();
  await conditions.nth(1).check();
  await expect(approve).toBeDisabled();
  await conditions.nth(2).check();
  await approve.click();
  await expect(page.getByRole('heading', { name: 'נמצאה שיטה שנבדקה', exact: true })).toBeVisible();
  await expect(page.getByText(/זהו תהליך פיזיקלי ולא תגובה כימית/)).toBeVisible();
});

test('the recorded Hebrew translation resolves the blockage location as the sink', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('איך אני פותח סתימה בכיור?');
  const interpreted = page.waitForResponse(item => item.url().endsWith('/api/interpret') && item.request().method() === 'POST');
  await page.getByRole('button', { name: 'Review my inputs', exact: true }).click();
  expect(await (await interpreted).json()).toMatchObject({
    intent: 'unclog', object_type: 'sink', surface: 'sink_drain',
    materials: 'not_stated', translated_text: 'How do I clear a clog in the sink?',
  });
  const approve = page.getByRole('button', { name: 'Confirm conditions and show unclogging steps', exact: true });
  await expect(approve).toBeDisabled();
  for (const condition of await page.getByRole('checkbox').all()) await condition.check();
  await approve.click();
  await expect(page.getByRole('heading', { name: 'Reviewed procedure available', exact: true })).toBeVisible();
});
