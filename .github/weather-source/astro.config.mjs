import { defineConfig } from 'astro/config';

// Static-first: every route is pre-rendered to its own directory/index.html,
// so deep links work on any plain static file server.
export default defineConfig({
  output: 'static',
  trailingSlash: 'always',
  devToolbar: { enabled: false },
  build: {
    format: 'directory',
    // Keep CSS and JS in external files so the Content-Security-Policy can be
    // "script-src 'self'; style-src 'self'" with no 'unsafe-inline'.
    inlineStylesheets: 'never',
    assets: 'assets',
  },
  vite: {
    build: { assetsInlineLimit: 0 },
  },
  server: { port: 4321, host: '127.0.0.1' },
  preview: { port: 4321, host: '127.0.0.1' },
});
