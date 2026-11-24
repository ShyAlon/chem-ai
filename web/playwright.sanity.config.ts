import { localTestConfig } from './playwright.shared';

const config = localTestConfig(8014, 4186, 'sanity.spec.ts');

export default {
  ...config,
  workers: 1,
  use: {
    ...config.use,
    trace: 'retain-on-failure' as const,
    screenshot: 'only-on-failure' as const,
  },
};
