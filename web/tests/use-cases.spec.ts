import { expect, test } from '@playwright/test';

test('all eight workspaces show a supported scenario, chemistry, and source in both languages', async ({ page }) => {
  await page.goto('/');
  const names = ['Stain removal', 'Food science', 'Limescale and corrosion', 'Material care', 'Water chemistry', 'Home experiments', 'Product-label explanations', 'Chemical disposal'];
  for (const name of names) {
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.locator('.use-case-workspace h2')).toHaveText(name);
    await expect(page.locator('.use-case-workspace ol li').first()).toBeVisible();
    await expect(page.locator('.use-case-workspace a')).toHaveAttribute('href', /^https:\/\//);
  }
  await page.getByRole('button', { name: 'עברית', exact: true }).click();
  const hebrew = ['הסרת כתמים', 'מדע המזון', 'אבנית וקורוזיה', 'התאמת חומרים', 'כימיית מים', 'ניסויים בבית', 'הסבר רכיבי מוצרים', 'פינוי חומרים כימיים'];
  for (const name of hebrew) {
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.locator('.use-case-workspace h2')).toHaveText(name);
  }
});

test('hardness thresholds, experiment measurements, and ingredient selection run deterministically', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Water chemistry', exact: true }).click();
  for (const [value, expected] of [['0', 'Soft'], ['60', 'Soft'], ['60.1', 'Moderately hard'], ['120', 'Moderately hard'], ['120.1', 'Hard'], ['180', 'Hard'], ['180.1', 'Very hard']]) {
    await page.getByLabel('Hardness (mg/L as CaCO₃)').fill(value);
    await page.getByRole('button', { name: 'Result', exact: true }).click();
    await expect(page.getByRole('status')).toHaveText(expected);
  }
  await page.getByRole('button', { name: 'Home experiments', exact: true }).click();
  await page.getByLabel('Stirred cup (seconds)', { exact: true }).fill('20');
  await page.getByLabel('Still cup (seconds)', { exact: true }).fill('60');
  await page.getByRole('button', { name: 'Compare measurements' }).click();
  await expect(page.getByRole('status')).toContainText('3.00');
  await page.getByRole('button', { name: 'Product-label explanations', exact: true }).click();
  await page.getByLabel('Ingredient class').selectOption('enzymes');
  await page.getByRole('button', { name: 'Explain ingredient' }).click();
  await expect(page.getByRole('status')).toContainText('Enzymes catalyze');
});
