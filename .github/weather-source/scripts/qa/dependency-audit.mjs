#!/usr/bin/env node
// Summarise the dependency footprint and run "npm audit".
// Contacts registry.npmjs.org only. A clean audit is not proof of security.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { ROOT } from './static-server.mjs';

const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
const lock = JSON.parse(fs.readFileSync(path.join(ROOT, 'package-lock.json'), 'utf8'));
const installed = Object.keys(lock.packages).filter((k) => k.startsWith('node_modules/'));
const exact = (deps = {}) => Object.entries(deps).map(([name, version]) => ({ name, version, exact: /^\d/.test(version) }));

let audit;
try {
  const out = execFileSync('npm', ['audit', '--json'], { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  audit = { ran: true, ...JSON.parse(out).metadata };
} catch (error) {
  // npm audit exits non-zero when it finds vulnerabilities; the JSON is still on stdout.
  try {
    audit = { ran: true, ...JSON.parse(error.stdout).metadata };
  } catch {
    audit = { ran: false, error: String(error.message).split('\n')[0] };
  }
}

const result = {
  schemaVersion: 1,
  generatedAtUtc: new Date().toISOString(),
  runtimeDependenciesShippedToBrowser: 0,
  directDependencies: { build: exact(pkg.dependencies), development: exact(pkg.devDependencies) },
  lockfile: { version: lock.lockfileVersion, installedPackages: installed.length },
  pythonTools: ['httpx', 'beautifulsoup4', 'lxml', 'pytest'],
  audit,
  caveat: 'npm audit reports known advisories for locked packages at the time it ran. It says nothing about unknown vulnerabilities, hosting or configuration.',
};
fs.writeFileSync(path.join(ROOT, 'data', 'normalized', 'dependency-audit.json'), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify({ installed: installed.length, audit: audit.vulnerabilities ?? audit }, null, 1));
