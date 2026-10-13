// Shared helpers for the end-to-end specs. Not a spec file itself.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test as base, expect, type Locator, type Page } from '@playwright/test';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
export const DIST_NAME = process.env.DIST_DIR ?? 'dist';
export const DIST = path.resolve(ROOT, DIST_NAME);
export const PACK = path.join(ROOT, 'data', 'source-snapshots', 'weather-source-pack');

/** Every route of the built site: one per index.html under the dist directory. */
export function discoverRoutes(): string[] {
  const routes: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name === 'index.html') {
        const relative = path.relative(DIST, dir).split(path.sep).filter(Boolean).join('/');
        routes.push(relative ? `/${relative}/` : '/');
      }
    }
  };
  if (!fs.existsSync(DIST)) throw new Error(`Build directory not found: ${DIST}`);
  walk(DIST);
  return routes.sort();
}

export const ROUTES = discoverRoutes();
export const routeExists = (route: string) => ROUTES.includes(route);
export const missingRoute = (route: string) => `route ${route} is not in the build (./${DIST_NAME}); the page has not been built yet`;

/** manifest.csv of the source pack, keyed by local file path. */
export function manifest(): Record<string, { url: string; bytes: number; sha256: string }> {
  const lines = fs.readFileSync(path.join(PACK, 'manifest.csv'), 'utf8').trim().split(/\r?\n/).slice(1);
  return Object.fromEntries(
    lines.map((line) => {
      const [url, file, , bytes, sha256] = line.split(',');
      return [file, { url, bytes: Number(bytes), sha256 }];
    }),
  );
}

/**
 * Data rows of a captured MAWN report, taken from the pack HTML with a plain
 * regular expression: the block is one line of &nbsp; and <br> in td.courier2.
 */
export function sourceReportRows(file: string): string[][] {
  const html = fs.readFileSync(path.join(PACK, file)).toString('latin1');
  const block = /<td class="courier2">([\s\S]*?)<\/td>/.exec(html)![1].trim();
  return block
    .replaceAll('<br>', '\n')
    .replaceAll('&nbsp;', ' ')
    .split('\n')
    .filter((line) => /^\d{2}\/\d{2}\/\d{2}\s/.test(line))
    .map((line) => line.trim().split(/\s+/));
}

export interface Audit {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: string[];
  badResponses: string[];
  /** Requests addressed to anything other than the test server. They are aborted, never sent. */
  externalRequests: string[];
}

/**
 * `test` with a guard that is always on: any request that is not addressed to
 * the local test server is aborted before it leaves the machine and recorded.
 * The same fixture collects console errors, page errors and failed requests.
 */
export const test = base.extend<{ audit: Audit }>({
  audit: [
    async ({ context, page, baseURL }, use) => {
      const origin = new URL(baseURL!).origin;
      const audit: Audit = { consoleErrors: [], pageErrors: [], failedRequests: [], badResponses: [], externalRequests: [] };
      const local = (url: string) => url.startsWith(`${origin}/`) || url === origin;
      const inert = (url: string) => /^(data|blob|about):/i.test(url);
      await context.route('**/*', (route) => {
        const url = route.request().url();
        if (local(url) || inert(url)) return route.continue();
        audit.externalRequests.push(`${route.request().method()} ${url} (${route.request().resourceType()})`);
        return route.abort('blockedbyclient');
      });
      page.on('request', (request) => {
        const url = request.url();
        if (!local(url) && !inert(url)) {
          const line = `${request.method()} ${url} (${request.resourceType()})`;
          if (!audit.externalRequests.includes(line)) audit.externalRequests.push(line);
        }
      });
      page.on('console', (message) => {
        if (message.type() === 'error') audit.consoleErrors.push(message.text());
      });
      page.on('pageerror', (error) => audit.pageErrors.push(error.message));
      page.on('requestfailed', (request) => audit.failedRequests.push(`${request.url()} (${request.failure()?.errorText ?? 'failed'})`));
      page.on('response', (response) => {
        if (response.status() >= 400) audit.badResponses.push(`${response.status()} ${response.url()}`);
      });
      await use(audit);
    },
    { auto: true },
  ],
});

export { expect };

/** Rows of a filterable list that are currently shown (no `hidden` attribute). */
export const shown = (rows: Locator) => rows.and(rows.page().locator(':not([hidden])'));

/** The first integer in a status line such as "Showing 19 of 119 stations". */
export async function firstNumber(locator: Locator): Promise<number> {
  const text = (await locator.textContent()) ?? '';
  const match = /\d+/.exec(text.replace(/,/g, ''));
  if (!match) throw new Error(`no number in status text: ${JSON.stringify(text)}`);
  return Number(match[0]);
}

/** Describe the focused element, for assertions and failure messages. */
export function focused(page: Page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return null;
    const box = el.getBoundingClientRect();
    return {
      tag: el.tagName.toLowerCase(),
      id: el.id,
      href: el.getAttribute('href'),
      text: (el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 80),
      visible: box.width > 0 && box.height > 0 && getComputedStyle(el).visibility !== 'hidden',
      inHiddenRow: Boolean(el.closest('[hidden]')),
      top: Math.round(box.top),
      left: Math.round(box.left),
      bottom: Math.round(box.bottom),
      right: Math.round(box.right),
    };
  });
}
