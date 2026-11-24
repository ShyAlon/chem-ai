import { expect, test } from '@playwright/test';

test('consumes all three MCP data tools and renders correlated activity traces', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Data lab', exact: true }).click();
  const compound = page.locator('.research-tool').filter({ has: page.getByRole('heading', { name: 'Compound lookup', exact: true }) });
  await compound.getByLabel('Compound name or CID').fill('water');
  await compound.getByRole('button', { name: 'Run lookup' }).click();
  await expect(compound.getByText('H2O', { exact: true })).toBeVisible();
  await expect(compound.getByRole('link', { name: 'PubChem', exact: true })).toHaveAttribute('href', /compound\/962$/);
  const activity = page.getByRole('complementary', { name: 'Activity trace', exact: true });
  await activity.getByRole('button', { name: /Activity trace/ }).click();
  await expect(activity.locator('.activity-kind').getByText('MCP', { exact: true })).toBeVisible();
  await expect(activity.locator('.activity-correlation code').first()).toHaveText(/^[a-f0-9]{32}$/);
  await compound.getByRole('button', { name: 'Run lookup' }).click();
  await expect(activity.locator('.activity-kind').getByText('Cache', { exact: true })).toBeVisible();
  await activity.getByRole('button', { name: /Activity trace/ }).click();

  const evidence = page.locator('.research-tool').filter({ has: page.getByRole('heading', { name: 'Chemistry evidence', exact: true }) });
  await evidence.getByLabel('Evidence query').fill('surfactants');
  await evidence.getByRole('button', { name: 'Run lookup' }).click();
  await expect(evidence.getByRole('heading', { name: 'How surfactants remove oily soil' })).toBeVisible();
  await expect(evidence.getByRole('link', { name: 'American Cleaning Institute' })).toBeVisible();

  const compare = page.locator('.research-tool').filter({ has: page.getByRole('heading', { name: 'Compare an experiment', exact: true }) });
  await compare.getByLabel('Water mass (g)').fill('99.802');
  await compare.getByLabel('Water volume (mL)').fill('100');
  await compare.getByLabel('Water temperature').selectOption('water-density-21');
  await compare.getByRole('button', { name: 'Run lookup' }).click();
  await expect(compare.getByText('+0.000%', { exact: true })).toBeVisible();
  await activity.getByRole('button', { name: /Activity trace/ }).click();
  await expect(activity.locator('.activity-kind').getByText('Calculation', { exact: true })).toBeVisible();
});

test('data tools support Hebrew and show a failed MCP request in the trace', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'עברית', exact: true }).click();
  await page.getByRole('button', { name: 'מעבדת נתונים', exact: true }).click();
  const compound = page.locator('.research-tool').filter({ has: page.getByRole('heading', { name: 'חיפוש תרכובות', exact: true }) });
  await compound.getByLabel('שם תרכובת או CID').fill('unavailable fixture');
  await compound.getByRole('button', { name: 'הרצת חיפוש' }).click();
  await expect(compound.getByRole('alert')).toBeVisible();
  const activity = page.getByRole('complementary', { name: 'תיעוד פעילות', exact: true });
  await activity.getByRole('button', { name: /תיעוד פעילות/ }).click();
  await expect(activity.locator('.activity-step.error')).toHaveCount(1);
});

test('compares free object data providers without assuming an Apple Watch material', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Data lab', exact: true }).click();
  const comparison = page.locator('.research-tool').filter({ has: page.getByRole('heading', { name: 'Object material comparison', exact: true }) });
  await comparison.getByLabel('Object or product name').fill('Apple Watch');
  await comparison.getByLabel('Component (optional)').fill('screen');
  await comparison.getByRole('button', { name: 'Run lookup' }).click();
  await expect(comparison.getByRole('heading', { name: 'wikidata', exact: true })).toBeVisible();
  await expect(comparison.getByRole('heading', { name: 'dbpedia', exact: true })).toBeVisible();
  await expect(comparison.getByText('Object candidates found, but no explicit material claims were returned.')).toHaveCount(2);
  await expect(comparison.getByRole('link', { name: 'wikidata', exact: true })).toHaveAttribute('href', /wikidata.org/);
  await page.getByRole('button', { name: 'Cleaning', exact: true }).click();
  await page.getByRole('textbox').fill('How do I clean the screen of my Apple Watch');
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByText('Object found; material not listed')).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Check procedure' })).toHaveCount(0);
});
