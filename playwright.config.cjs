const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.cjs',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  timeout: 30000,
  reporter: [['list'], ['html', { open: 'never' }], ['junit', { outputFile: 'test-results/e2e.xml' }]],
  use: {
    browserName: 'chromium',
    acceptDownloads: true,
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: ['http', 'file'].flatMap(transport => [
    { name: `chromium-desktop-${transport}`, metadata: { transport }, use: { viewport: { width: 1440, height: 1000 } } },
    { name: `chromium-mobile-${transport}`, metadata: { transport }, use: { viewport: { width: 390, height: 844 } } }
  ]),
  webServer: {
    command: 'python3 tools/serve_e2e.py',
    url: 'http://127.0.0.1:4173/index.html',
    reuseExistingServer: false,
    timeout: 30000
  }
});
