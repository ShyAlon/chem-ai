import { defineConfig } from '@playwright/test';

export function localTestConfig(apiPort: number, webPort: number, testMatch?: string) {
  const apiURL = `http://127.0.0.1:${apiPort}`;
  const webURL = `http://127.0.0.1:${webPort}`;
  return defineConfig({
    testDir: './tests',
    ...(testMatch ? { testMatch } : {}),
    use: {
      baseURL: webURL,
      browserName: 'chromium',
      locale: 'en-US',
      launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
        : {},
    },
    webServer: [
      { command: `TEST_API_PORT=${apiPort} ../scripts/serve-test-api.sh`, url: `${apiURL}/api/health` },
      {
        command: `HOMECHEM_API_URL=${apiURL} npm run preview -- --host 127.0.0.1 --port ${webPort}`,
        url: webURL,
      },
    ],
  });
}
