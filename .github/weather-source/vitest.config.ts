import { defineConfig } from 'vitest/config';

// Unit tests only. Playwright specs live in tests/e2e and pytest files in
// tests/python; neither may be collected by vitest.
export default defineConfig({
  test: {
    include: ['tests/unit/**/*.test.ts'],
    environment: 'node',
    watch: false,
  },
});
