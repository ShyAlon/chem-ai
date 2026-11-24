import { expect, test } from '@playwright/test';

test('reviews the same procedure in both languages and persists Hebrew', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Try an example' }).click();
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm these details' })).toBeVisible();
  await page.getByRole('button', { name: 'Check procedure' }).click();
  await expect(page.getByRole('heading', { name: 'Reviewed procedure available' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'American Cleaning Institute screen care' })).toHaveAttribute('href', /cleaninginstitute\.org/);
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
  await expect(page.getByText('glass_screen_dry_cleaning', { exact: true })).toBeVisible();
});

test('keeps unsupported inputs outside the reviewed procedure', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('My display has nano-texture glass.');
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByRole('heading', { name: 'No reviewed procedure found' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Check procedure' })).toHaveCount(0);
});

test('a rate-limited question displays Retry-After and can be submitted again', async ({ page }) => {
  await page.route('**/api/interpret', route => route.fulfill({
    status: 429, headers: { 'Retry-After': '2' }, json: { detail: 'rate_limited' },
  }), { times: 1 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Try an example' }).click();
  const submit = page.getByRole('button', { name: 'Review my inputs' });
  await submit.click();
  await expect(page.getByRole('status')).toHaveText(/Try another question in [12] seconds?\./);
  await expect(submit).toBeDisabled();
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByRole('heading', { name: 'Confirm these details' })).toBeVisible();
});

test('confirms missing tabletop materials and logs the decision as an object', async ({ page }) => {
  await page.goto('/');
  const originalText = '  I want to clean my glass table  ';
  await page.getByRole('textbox').fill(originalText);
  const interpreted = page.waitForEvent('console', message =>
    message.type() === 'info' && message.text().includes('homechem.attempt'));
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByText('Confirm that the glass is intact and uncoated.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Reviewed procedure available' })).toHaveCount(0);
  expect(await (await interpreted).args()[0].jsonValue()).toMatchObject({
    action: 'interpret',
    originalText,
  });

  const logged = page.waitForEvent('console', message =>
    message.type() === 'info' && message.text().includes('homechem.attempt'));
  await page.getByRole('button', { name: 'I will use only water and a microfiber cloth' }).click();
  await expect(page.getByRole('link', { name: 'Documentary Heritage and Preservation Services cleaning guide' })).toBeVisible();
  const [summary] = (await logged).args();
  expect(await summary.jsonValue()).toEqual({
    event: 'homechem.attempt',
    action: 'assess',
    originalText,
    locale: 'en',
    requestId: expect.stringMatching(/^[0-9a-f]{32}$/),
    traceId: expect.stringMatching(/^[0-9a-f]{32}$/),
    activityUrl: expect.stringMatching(/\/api\/activities\/[0-9a-f]{32}$/),
    httpStatus: 200,
    elapsedMs: expect.any(Number),
    outcome: 'success',
    decision: 'approved',
    rule: 'glass_table_water_cleaning',
    policyVersion: expect.any(String),
  });
});

test('Enter reviews the question and Control+Enter inserts a line break', async ({ page }) => {
  await page.goto('/');
  const question = page.getByRole('textbox');
  await question.fill('First line');
  await question.press('End');
  await question.press('Control+Enter');
  await expect(question).toHaveValue('First line\n');
  await expect(page.getByRole('button', { name: 'Review my inputs' })).toBeEnabled();

  await page.getByRole('button', { name: 'Try an example' }).click();
  await question.press('Enter');
  await expect(page.getByRole('heading', { name: 'Confirm these details' })).toBeVisible();
});

test('the header and footer stay in place as the notebook scrolls', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 480 });
  await page.goto('/');
  const header = page.getByRole('banner');
  const footer = page.getByRole('contentinfo');
  const headerBefore = await header.boundingBox();
  const footerBefore = await footer.boundingBox();

  const notebook = page.getByRole('main');
  await notebook.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect.poll(() => notebook.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  await expect(header).toBeInViewport({ ratio: 1 });
  await expect(footer).toBeInViewport({ ratio: 1 });
  expect(await header.boundingBox()).toEqual(headerBefore);
  expect(await footer.boundingBox()).toEqual(footerBefore);
});

test('the backdrop responds to the pointer and stays still with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const canvas = page.locator('.chemistry-backdrop canvas');
  const image = () => canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL());
  await expect.poll(() => canvas.evaluate(element => (element as HTMLCanvasElement).width)).toBeGreaterThan(300);
  const stillFrame = await image();
  const main = await page.getByRole('main').boundingBox();
  if (!main) throw new Error('Notebook is missing');
  await page.mouse.move(main.x + 20, main.y + 20);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  expect(await image()).toBe(stillFrame);

  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.mouse.move(main.x + 40, main.y + 35);
  await expect.poll(image).not.toBe(stillFrame);
});

test('offers a reviewed procedure for everyday cleaning of a ceramic sink', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('I want to clean my ceramic sink');
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByText(/Confirm that the sink has an intact ceramic glaze/)).toBeVisible();
  await page.getByRole('button', { name: 'I will use warm water, mild dish soap, and a soft cloth' }).click();
  await expect(page.getByRole('link', { name: 'American Cleaning Institute chemistry of cleaning' })).toBeVisible();
  await expect(page.getByText('Rinse the basin thoroughly with clean water.')).toBeVisible();
});

test('resolves a ceramic floor into separate fields and confirms the floor procedure', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('I want to clean my ceramic floor');
  const logged = page.waitForEvent('console', message =>
    message.type() === 'info' && message.text().includes('homechem.attempt'));
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByText('Ceramic', { exact: true })).toBeVisible();
  await expect(page.getByText('Floor', { exact: true })).toBeVisible();
  await expect(page.getByText('Not specified', { exact: true })).toBeVisible();
  expect(await (await logged).args()[0].jsonValue()).toMatchObject({
    method: 'dictionary', objectType: 'floor', substrate: 'ceramic', finish: null,
  });
  await page.getByRole('button', { name: 'I will use only water and a clean mop' }).click();
  await expect(page.getByRole('link', { name: 'Porcelain and ceramic tile care' })).toBeVisible();
});

test('asks for the screen material even when the device brand is recognized', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('I want to clean the screen of my iPad');
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByText(/Tell Fix-It what the exposed screen surface is made of/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Check procedure' })).toHaveCount(0);
});

test('uses the same material procedure for a glass laptop screen', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('I want to clean my glass laptop screen');
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  await expect(page.getByText('Glass', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'I will use a clean, dry microfiber cloth' }).click();
  await expect(page.getByText(/fibers pick up loose particles/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'American Cleaning Institute screen care' })).toBeVisible();
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
  await page.getByRole('link', { name: 'How it works' }).click();
  await expect(page).toHaveURL(/\/how-it-works$/);
  await expect(page.getByRole('heading', { name: 'How does it work?' })).toBeVisible();
});

test('the algorithm guide is directly accessible and supports Hebrew', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/how-it-works');
  await expect(page.getByRole('heading', { name: 'How does it work?' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Confirm details and check the catalog' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'How it works' })).toHaveAttribute('aria-current', 'page');
  await page.getByRole('button', { name: 'עברית' }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { name: 'איך זה עובד?' })).toBeVisible();
  await page.getByRole('link', { name: 'חזרה למחברת הפתרונות' }).click();
  await expect(page.getByRole('textbox')).toBeVisible();
});

test('an unresolved keyboard question still searches MCP and explains the empty result', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('How do I clean my mac keyboard');
  const loggedAttempt = page.waitForEvent('console', { predicate: message => message.type() === 'info' && message.text().includes('homechem.attempt') });
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  const summary = await (await loggedAttempt).args()[0].jsonValue();
  expect(summary.diagnostics.unrecognized_tokens).toEqual(['mac']);
  expect(summary.diagnostics.reason_codes).not.toContain('model_no_catalog_match');
  expect(summary.evidenceSearchedDocuments).toBe(4);
  expect(summary.traceId).toMatch(/^[a-f0-9]{32}$/);
  expect(summary.activityUrl).toContain('/api/activities/');
  await expect(page.getByRole('heading', { name: 'No reviewed procedure found' })).toBeVisible();
  await expect(page.getByText('The MCP evidence search found no matching sources in the current library.')).toBeVisible();
  const activity = page.getByRole('complementary', { name: 'Activity trace', exact: true });
  await activity.getByRole('button', { name: /Activity trace/ }).click();
  await expect(activity.locator('.activity-kind').getByText('MCP', { exact: true })).toBeVisible();
  await expect(activity.getByText('evidence.search', { exact: true })).toBeVisible();
  const normalization = activity.locator('.activity-step').filter({ hasText: 'normalization.resolve' });
  await normalization.locator('summary').click();
  await expect(normalization.locator('pre')).toContainText('"keyboard"');
  await expect(normalization).toContainText('material_not_identified');
  expect(summary.objectType).toBe('keyboard');
  expect(summary.resolutionStatus).toBe('needs_details');
  await expect(activity.getByText('nlp.spacy', { exact: true })).toBeVisible();
  const retrieval = activity.locator('.activity-step').filter({ hasText: 'evidence.search' });
  await retrieval.locator('summary').click();
  await expect(retrieval.locator('pre')).toContainText('How do I clean my mac keyboard');
  await expect(page.getByRole('button', { name: 'Check procedure' })).toHaveCount(0);
});

test('downloads the selected request debug ZIP from the activity panel', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('Clean my ceramic sink');
  await page.getByRole('button', { name: 'Review my inputs' }).click();
  const activity = page.getByRole('complementary', { name: 'Activity trace', exact: true });
  const button = activity.getByRole('button', { name: 'Download debug ZIP' });
  await expect(button).toBeEnabled();
  // Export remains accessible while the detailed timeline is collapsed.
  const downloaded = page.waitForEvent('download');
  await button.click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toMatch(/^homechem-debug-[a-f0-9]{32}\.zip$/);
  expect(await file.failure()).toBeNull();
  await page.route('**/api/activities/*/download', route => route.fulfill({ status: 404, body: '{}' }));
  await button.click();
  await expect(activity.getByRole('alert')).toContainText('Download unavailable');
});
