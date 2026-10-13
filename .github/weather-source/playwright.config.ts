import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

// End-to-end tests run only against the locally built static site, served by
// scripts/qa/static-server.mjs on 127.0.0.1 with the headers from
// deploy/security-headers.json. They never contact a legacy or other remote host.
//
//   npx astro build && npx playwright test                      (uses ./dist)
//   DIST_DIR=dist-agent-b npx playwright test                   (another build directory)
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = 4399;
const DIST_DIR = process.env.DIST_DIR ?? 'dist';
const BASE_URL = `http://127.0.0.1:${PORT}`;

if (!fs.existsSync(path.resolve(ROOT, DIST_DIR, 'index.html'))) {
  throw new Error(`No built site at ./${DIST_DIR}/index.html. Build first (for example: npx astro build --outDir ${DIST_DIR}).`);
}

export default defineConfig({
  testDir: 'tests/e2e',
  outputDir: 'test-results',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: [['list'], ['json', { outputFile: 'reports/e2e-results.json' }]],
  use: {
    baseURL: BASE_URL,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    acceptDownloads: true,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          // Belt and braces for the "no remote requests" rule: the browser cannot
          // resolve any host name at all. tests/e2e/helpers.ts also aborts and
          // records every request that is not addressed to the test server.
          args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'],
        },
      },
    },
  ],
  webServer: {
    command: 'node scripts/qa/static-server.mjs',
    url: `${BASE_URL}/`,
    reuseExistingServer: false,
    env: { PORT: String(PORT), DIST_DIR },
    stdout: 'ignore',
    stderr: 'pipe',
    timeout: 30_000,
  },
});
