import { expect, test } from '@playwright/test';

test('sanity: reviews a question, approves a procedure, exports diagnostics, and persists Hebrew', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('pageerror', error => browserErrors.push(error.message));

  await page.goto('/');
  await page.getByRole('button', { name: 'Try an example', exact: true }).click();
  const question = await page.getByRole('textbox').inputValue();
  expect(question.trim()).not.toBe('');

  const interpretationResponse = page.waitForResponse(response =>
    response.url().endsWith('/api/interpret') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Review my inputs', exact: true }).click();
  const interpreted = await interpretationResponse;
  expect(interpreted.status()).toBe(200);
  expect(interpreted.request().postDataJSON()).toEqual({ text: question });
  expect(await interpreted.json()).toMatchObject({
    method: 'dictionary', resolution_status: 'ready_for_confirmation',
  });
  await expect(page.getByRole('heading', { name: 'Confirm these details', exact: true })).toBeVisible();

  const assessmentResponse = page.waitForResponse(response =>
    response.url().endsWith('/api/assess') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Check procedure', exact: true }).click();
  const assessed = await assessmentResponse;
  expect(assessed.status()).toBe(200);
  expect(await assessed.json()).toMatchObject({ status: 'approved' });
  await expect(page.getByRole('heading', { name: 'Reviewed procedure available', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Why it works', exact: true })).toBeVisible();

  const activity = page.getByRole('complementary', { name: 'Activity trace', exact: true });
  await activity.getByRole('button', { name: /Activity trace/ }).click();
  await expect(activity.getByText('policy.assess', { exact: true })).toBeVisible();
  // A real local MCP transport must succeed, including when its result is cached.
  await expect(activity.locator('.activity-step.success').filter({ hasText: /mcp\.data|knowledge\.cache/ })).toHaveCount(1);
  await expect(activity.locator('.activity-correlation code').first()).toHaveText(assessed.headers()['x-request-id']);

  const downloaded = page.waitForEvent('download');
  await activity.getByRole('button', { name: 'Download debug ZIP', exact: true }).click();
  const archive = await downloaded;
  expect(archive.suggestedFilename()).toBe(`homechem-debug-${assessed.headers()['x-request-id']}.zip`);
  expect(await archive.failure()).toBeNull();

  await page.getByRole('button', { name: 'עברית', exact: true }).click();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'he');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('button', { name: 'בדיקת הפרטים', exact: true })).toBeVisible();
  expect(browserErrors).toEqual([]);
});

for (const scenario of [
  { question: 'how do I clean my apple watch', object: 'watch', productQuery: 'apple watch' },
  { question: 'how do I unclog my sink?', object: 'sink', productQuery: null },
  { question: 'How do I clear a clog in the sink?', object: 'sink', productQuery: null },
]) {
  test(`sanity: ${scenario.question}`, async ({ page }) => {
    const browserErrors: string[] = [];
    page.on('pageerror', error => browserErrors.push(error.message));
    await page.goto('/');
    await page.getByRole('textbox').fill(scenario.question);

    const interpretationResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/interpret') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Review my inputs', exact: true }).click();
    const response = await interpretationResponse;
    expect(response.status()).toBe(200);
    expect(response.request().postDataJSON()).toEqual({ text: scenario.question });
    const result = await response.json();
    let latestResponse = response;
    expect(result).toMatchObject({
      method: 'dictionary', object_type: scenario.object, substrate: null,
    });

    if (scenario.productQuery) {
      expect(result.surface).toBe('unknown');
      expect(result.presentation.en.assessment).toBeNull();
      await expect(page.getByRole('heading', { name: 'No reviewed procedure found', exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Check procedure', exact: true })).toHaveCount(0);
      expect(result.object_materials.query).toBe(scenario.productQuery);
      expect(result.object_materials.providers.map((provider: { provider: string }) => provider.provider))
        .toEqual(['wikidata', 'dbpedia']);
      expect(result.object_materials.requires_confirmation).toBe(true);
      await expect(page.getByText('Object found; material not listed', { exact: true })).toHaveCount(2);
    } else {
      expect(result.intent).toBe('unclog');
      expect(result.surface).toBe('sink_drain');
      expect(result.object_materials).toBeNull();
      await expect(page.getByRole('heading', { name: 'Confirm these details', exact: true })).toBeVisible();
      const approve = page.getByRole('button', { name: 'Confirm conditions and show unclogging steps', exact: true });
      await expect(approve).toBeDisabled();
      const conditions = page.getByRole('checkbox');
      await expect(conditions).toHaveCount(3);
      for (const condition of await conditions.all()) await condition.check();
      const assessed = page.waitForResponse(item => item.url().endsWith('/api/assess') && item.request().method() === 'POST');
      await approve.click();
      latestResponse = await assessed;
      expect(await latestResponse.json()).toMatchObject({ status: 'approved', rule: 'sink_drain_mechanical_unclogging' });
      await expect(page.getByRole('heading', { name: 'Reviewed procedure available', exact: true })).toBeVisible();
      await expect(page.getByText(/The water and sealed cup transmit alternating pressure/)).toBeVisible();
    }

    const activity = page.getByRole('complementary', { name: 'Activity trace', exact: true });
    await activity.getByRole('button', { name: /Activity trace/ }).click();
    await expect(activity.getByText('evidence.search', { exact: true })).toBeVisible();
    await expect(activity.locator('.activity-correlation code').first()).toHaveText(latestResponse.headers()['x-request-id']);
    await expect(activity.getByRole('button', { name: 'Download debug ZIP', exact: true })).toBeEnabled();
    expect(browserErrors).toEqual([]);
  });
}
