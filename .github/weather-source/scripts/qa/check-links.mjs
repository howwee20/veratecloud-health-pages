#!/usr/bin/env node
// Static link checker for the built site. No browser and no network.
//
//   node scripts/qa/check-links.mjs                 (checks ./dist)
//   DIST_DIR=dist-agent-b node scripts/qa/check-links.mjs
//
// Walks the build directory, reads every .html file and collects URL-bearing
// attributes (href, src, srcset, poster, action, data and SVG xlink:href) from
// every element, which covers <a>, <a download>, <link>, <script>, <img> and
// <area>. For each reference:
//
//   * internal  -> the target file must exist in the build (a directory
//                  resolves to its index.html), and a #fragment must be the id
//                  (or <a name>) of an element in the target page;
//   * external  -> listed, grouped by host. External URLs are NEVER requested,
//                  so this script says nothing about whether they work.
//
// Writes reports/link-check.json and exits 1 if an internal link or fragment
// is broken.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const DIST_NAME = process.env.DIST_DIR ?? 'dist';
const DIST = path.resolve(ROOT, DIST_NAME);
const REPORT = path.join(ROOT, 'reports', 'link-check.json');
const FAKE_ORIGIN = 'http://site.invalid';
const URL_ATTRIBUTES = ['href', 'src', 'srcset', 'poster', 'action', 'data', 'xlink:href'];

if (!fs.existsSync(DIST) || !fs.statSync(DIST).isDirectory()) {
  console.error(`check-links: build directory not found: ${DIST}\nBuild the site first, or set DIST_DIR.`);
  process.exit(2);
}

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

const toPosix = (file) => path.relative(DIST, file).split(path.sep).join('/');

/** URL path a browser would use for a built .html file. */
function urlPathOf(relative) {
  if (relative === 'index.html') return '/';
  if (relative.endsWith('/index.html')) return `/${relative.slice(0, -'index.html'.length)}`;
  return `/${relative}`;
}

// ---------------------------------------------------------------------------
// A small, tolerant HTML scanner: tags and their attributes, nothing more.
// ---------------------------------------------------------------------------

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };

function decodeEntities(value) {
  return value.replace(/&(#x[0-9a-f]+|#\d+|[a-z][a-z0-9]*);/gi, (whole, body) => {
    if (body[0] === '#') {
      const code = body[1].toLowerCase() === 'x' ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : whole;
    }
    return ENTITIES[body.toLowerCase()] ?? whole;
  });
}

function parseAttributes(source) {
  const attributes = {};
  const pattern = /([^\s"'<>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  for (const match of source.matchAll(pattern)) {
    const name = match[1].toLowerCase();
    if (name in attributes) continue; // the first occurrence wins, as in browsers
    attributes[name] = decodeEntities(match[2] ?? match[3] ?? match[4] ?? '');
  }
  return attributes;
}

/** Yields { tag, attributes } for every start tag outside comments, <script> and <style> bodies. */
function* startTags(html) {
  const pattern = /<!--[\s\S]*?-->|<(script|style)\b((?:"[^"]*"|'[^']*'|[^'">])*)>[\s\S]*?<\/\1\s*>|<([a-zA-Z][^\s\/>]*)((?:"[^"]*"|'[^']*'|[^'">])*)>/gi;
  for (const match of html.matchAll(pattern)) {
    if (match[0].startsWith('<!--')) continue;
    if (match[1]) yield { tag: match[1].toLowerCase(), attributes: parseAttributes(match[2]) };
    else yield { tag: match[3].toLowerCase(), attributes: parseAttributes(match[4]) };
  }
}

function scan(html) {
  const ids = new Set();
  const duplicateIds = new Set();
  const references = [];
  for (const { tag, attributes } of startTags(html)) {
    if (attributes.id) {
      if (ids.has(attributes.id)) duplicateIds.add(attributes.id);
      ids.add(attributes.id);
    }
    if (tag === 'a' && attributes.name) ids.add(attributes.name);
    for (const attribute of URL_ATTRIBUTES) {
      if (!(attribute in attributes)) continue;
      if (attribute === 'data' && tag !== 'object') continue;
      if (attribute === 'action' && tag !== 'form') continue;
      const raw = attributes[attribute];
      const values = attribute === 'srcset' ? raw.split(',').map((part) => part.trim().split(/\s+/)[0]) : [raw];
      for (const value of values) {
        references.push({ tag, attribute, value: value.trim(), download: tag === 'a' && 'download' in attributes, rel: attributes.rel ?? null });
      }
    }
  }
  return { ids, duplicateIds: [...duplicateIds], references };
}

// ---------------------------------------------------------------------------
// Check
// ---------------------------------------------------------------------------

const files = walk(DIST);
const fileSet = new Set(files.map(toPosix));
const dirSet = new Set();
for (const relative of fileSet) {
  const parts = relative.split('/');
  for (let i = 1; i < parts.length; i += 1) dirSet.add(parts.slice(0, i).join('/'));
}
const htmlFiles = [...fileSet].filter((relative) => relative.endsWith('.html')).sort();
const pages = new Map(htmlFiles.map((relative) => [relative, scan(fs.readFileSync(path.join(DIST, relative), 'utf8'))]));

/** Map a site-absolute URL path to a file in the build, or explain why it does not resolve. */
function resolveInternal(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return { file: null, reason: 'path is not valid percent-encoding' };
  }
  const relative = decoded.replace(/^\/+/, '');
  if (relative === '' || relative.endsWith('/')) {
    const index = `${relative}index.html`;
    return fileSet.has(index) ? { file: index } : { file: null, reason: `no ${index} in the build` };
  }
  if (fileSet.has(relative)) return { file: relative };
  if (dirSet.has(relative)) {
    const index = `${relative}/index.html`;
    return fileSet.has(index)
      ? { file: index, note: 'directory linked without a trailing slash; static hosts answer with a redirect' }
      : { file: null, reason: `directory without index.html: ${relative}/` };
  }
  return { file: null, reason: `no such file in the build: ${relative}` };
}

const broken = [];
const brokenFragments = [];
const warnings = [];
const otherSchemes = [];
const external = new Map(); // host -> Map(url -> Set(pages))
const externalEmbeds = []; // external resources a browser would fetch without the user asking
const internalTargets = new Set();
const byElement = {};
let referenceCount = 0;
let internalCount = 0;
let externalCount = 0;
let fragmentCount = 0;

for (const [relative, { references, duplicateIds }] of pages) {
  const pagePath = urlPathOf(relative);
  // A repeated id makes fragment links and aria references ambiguous.
  for (const id of duplicateIds) warnings.push({ page: pagePath, element: 'id', link: `#${id}`, note: `id="${id}" is used more than once on this page` });
  for (const reference of references) {
    referenceCount += 1;
    const where = `${reference.tag}[${reference.attribute}]${reference.download ? ' (download)' : ''}`;
    byElement[where] = (byElement[where] ?? 0) + 1;
    const value = reference.value;
    if (value === '') {
      broken.push({ page: pagePath, element: where, link: value, reason: 'empty URL' });
      continue;
    }
    let url;
    try {
      url = new URL(value, FAKE_ORIGIN + pagePath);
    } catch {
      broken.push({ page: pagePath, element: where, link: value, reason: 'not a valid URL' });
      continue;
    }
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      otherSchemes.push({ page: pagePath, element: where, link: value, scheme: url.protocol.replace(':', '') });
      continue;
    }
    if (url.origin !== FAKE_ORIGIN) {
      externalCount += 1;
      const host = url.host;
      if (!external.has(host)) external.set(host, new Map());
      const urls = external.get(host);
      if (!urls.has(url.href)) urls.set(url.href, new Set());
      urls.get(url.href).add(pagePath);
      const navigational = reference.tag === 'a' || reference.tag === 'area' || reference.tag === 'form'
        || (reference.tag === 'link' && !/\b(stylesheet|icon|preload|modulepreload|prefetch|preconnect|dns-prefetch|manifest)\b/i.test(reference.rel ?? ''));
      if (!navigational) externalEmbeds.push({ page: pagePath, element: where, link: value });
      continue;
    }

    internalCount += 1;
    const target = resolveInternal(url.pathname);
    if (!target.file) {
      broken.push({ page: pagePath, element: where, link: value, resolved: url.pathname, reason: target.reason });
      continue;
    }
    internalTargets.add(url.pathname);
    if (target.note) warnings.push({ page: pagePath, element: where, link: value, note: target.note });

    const fragment = url.hash.slice(1);
    if (fragment === '') continue;
    fragmentCount += 1;
    let id;
    try {
      id = decodeURIComponent(fragment);
    } catch {
      id = fragment;
    }
    if (!target.file.endsWith('.html')) {
      warnings.push({ page: pagePath, element: where, link: value, note: 'fragment on a non-HTML file was not checked' });
      continue;
    }
    // Per the HTML standard "#top" scrolls to the top of the page when no element has that id.
    if (id.toLowerCase() === 'top') continue;
    if (!pages.get(target.file).ids.has(id)) {
      brokenFragments.push({ page: pagePath, element: where, link: value, target: urlPathOf(target.file), fragment: id, reason: `no element with id="${id}" in ${urlPathOf(target.file)}` });
    }
  }
}

// Pages that nothing links to are not errors, but they are worth knowing about.
const linkedFiles = new Set([...internalTargets].map((pathname) => resolveInternal(pathname).file));
const orphanPages = htmlFiles.filter((relative) => relative !== 'index.html' && relative !== '404.html' && !linkedFiles.has(relative)).map(urlPathOf);

const externalReport = [...external.entries()]
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([host, urls]) => ({
    host,
    linkCount: [...urls.values()].reduce((n, set) => n + set.size, 0),
    urls: [...urls.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([url, set]) => ({ url, insecure: url.startsWith('http://'), pages: [...set].sort() })),
  }));

const report = {
  tool: 'scripts/qa/check-links.mjs',
  generatedAtUtc: new Date().toISOString(),
  distDir: DIST_NAME,
  method: 'Static analysis of the built HTML. Internal links and fragments are resolved against files in the build directory. External links are listed only; they were not requested, so their status is unknown.',
  summary: {
    htmlFiles: htmlFiles.length,
    filesInBuild: fileSet.size,
    references: referenceCount,
    internalReferences: internalCount,
    uniqueInternalTargets: internalTargets.size,
    fragmentsChecked: fragmentCount,
    brokenInternalLinks: broken.length,
    brokenFragments: brokenFragments.length,
    warnings: warnings.length,
    externalReferences: externalCount,
    externalHosts: externalReport.length,
    externalUrls: externalReport.reduce((n, host) => n + host.urls.length, 0),
    externalUrlsOverPlainHttp: externalReport.reduce((n, host) => n + host.urls.filter((u) => u.insecure).length, 0),
    externalLinksRequested: 0,
    externalEmbeds: externalEmbeds.length,
    otherSchemeReferences: otherSchemes.length,
    pagesWithNoInboundLink: orphanPages.length,
  },
  referencesByElement: Object.fromEntries(Object.entries(byElement).sort(([a], [b]) => a.localeCompare(b))),
  brokenInternalLinks: broken,
  brokenFragments,
  warnings,
  otherSchemes,
  externalEmbeds,
  pagesWithNoInboundLink: orphanPages,
  pages: htmlFiles.map(urlPathOf),
  external: externalReport,
};

fs.mkdirSync(path.dirname(REPORT), { recursive: true });
fs.writeFileSync(REPORT, `${JSON.stringify(report, null, 2)}\n`);

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

const s = report.summary;
console.log(`Link check of ${path.isAbsolute(DIST_NAME) ? DIST_NAME : `./${DIST_NAME}`}: ${s.htmlFiles} HTML files, ${s.references} references`);
console.log(`  internal: ${s.internalReferences} references to ${s.uniqueInternalTargets} distinct targets, ${s.fragmentsChecked} with a fragment`);
console.log(`  broken internal links: ${s.brokenInternalLinks}`);
for (const item of broken.slice(0, 50)) console.log(`    ${item.page}  ${item.element}  ${JSON.stringify(item.link)}  -> ${item.reason}`);
if (broken.length > 50) console.log(`    ... and ${broken.length - 50} more (see the JSON report)`);
console.log(`  broken fragments: ${s.brokenFragments}`);
for (const item of brokenFragments.slice(0, 50)) console.log(`    ${item.page}  ${item.element}  ${JSON.stringify(item.link)}  -> ${item.reason}`);
if (brokenFragments.length > 50) console.log(`    ... and ${brokenFragments.length - 50} more (see the JSON report)`);
if (warnings.length) {
  console.log(`  warnings: ${warnings.length}`);
  for (const item of warnings.slice(0, 20)) console.log(`    ${item.page}  ${JSON.stringify(item.link)}  -> ${item.note}`);
}
if (otherSchemes.length) {
  console.log(`  other schemes (not checked): ${otherSchemes.length}`);
  for (const item of otherSchemes.slice(0, 20)) console.log(`    ${item.page}  ${item.element}  ${JSON.stringify(item.link)}`);
}
if (orphanPages.length) console.log(`  pages with no inbound link: ${orphanPages.join(', ')}`);
console.log(`  external (NOT requested): ${s.externalReferences} references, ${s.externalUrls} distinct URLs on ${s.externalHosts} hosts, ${s.externalUrlsOverPlainHttp} over plain http`);
for (const host of externalReport) console.log(`    ${host.host}  ${host.urls.length} URL${host.urls.length === 1 ? '' : 's'}, ${host.linkCount} page reference${host.linkCount === 1 ? '' : 's'}`);
if (externalEmbeds.length) {
  console.log(`  WARNING: ${externalEmbeds.length} external resource(s) would be fetched automatically by a browser (images, scripts, stylesheets, frames):`);
  for (const item of externalEmbeds.slice(0, 20)) console.log(`    ${item.page}  ${item.element}  ${JSON.stringify(item.link)}`);
} else {
  console.log('  external embeds (images, scripts, stylesheets, frames loaded from other hosts): 0');
}
console.log(`  report: ${path.relative(ROOT, REPORT)}`);

if (broken.length > 0 || brokenFragments.length > 0) {
  console.error(`check-links: FAILED (${broken.length} broken internal link(s), ${brokenFragments.length} broken fragment(s))`);
  process.exit(1);
}
const legacyHosts = externalReport.filter(x=>['mawn.geo.msu.edu','agweather.geo.msu.edu','www.agweather.geo.msu.edu','climate.geo.msu.edu'].includes(x.host));
if(legacyHosts.length){console.error('check-links: legacy-host navigation escaped local routing',legacyHosts.map(x=>x.host));process.exit(1);}
console.log('check-links: OK (no broken internal links, fragments, or legacy-host navigation; other external links were not requested)');
