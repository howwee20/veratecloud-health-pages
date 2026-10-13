// Keeps the hosting examples in deploy/ in step with deploy/security-headers.json
// and deploy/legacy-url-map.csv. This checks the text of the example files; it
// does not show that nginx, Apache or a hosting service behaves as intended.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const read = (relative: string) => readFileSync(`${ROOT}${relative}`, 'utf8');
const headers = JSON.parse(read('deploy/security-headers.json')) as { all: Record<string, string>; httpsOnly: Record<string, string> };

/** Lines that are configuration, not comments. */
const active = (text: string) => text.split('\n').filter((line) => line.trim() !== '' && !line.trim().startsWith('#'));
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const nginx = active(read('deploy/nginx.conf.example'));
const apache = active(read('deploy/apache.htaccess.example'));
const netlify = active(read('deploy/_headers'));

describe('security-headers.json', () => {
  it('still has the shape the examples were written for', () => {
    expect(Object.keys(headers.all).sort()).toEqual([
      'Content-Security-Policy', 'Cross-Origin-Opener-Policy', 'Permissions-Policy', 'Referrer-Policy', 'X-Content-Type-Options', 'X-Frame-Options',
    ]);
    expect(Object.keys(headers.httpsOnly)).toEqual(['Strict-Transport-Security']);
    // The policy the tests rely on: nothing inline, nothing from another origin.
    expect(headers.all['Content-Security-Policy'].replace('form-action https://mawn.geo.msu.edu;', '')).not.toMatch(/unsafe-inline|unsafe-eval|https?:|\*/);
    expect(headers.all['Content-Security-Policy']).toContain('form-action https://mawn.geo.msu.edu;');
  });
});

describe('nginx.conf.example', () => {
  for (const [name, value] of Object.entries({ ...headers.all, ...headers.httpsOnly })) {
    it(`sets ${name} to the exact value, with "always"`, () => {
      const matches = nginx.filter((line) => new RegExp(`^\\s*add_header\\s+${escape(name)}\\s`).test(line));
      expect(matches).toHaveLength(1);
      expect(matches[0].trim()).toBe(`add_header ${name} "${value}" always;`);
    });
  }

  it('sends Strict-Transport-Security from the TLS server block only', () => {
    const text = nginx.join('\n');
    const blocks = text.split(/^server \{/m).slice(1);
    expect(blocks).toHaveLength(2);
    const [plain, tls] = blocks;
    expect(plain).toMatch(/listen 80;/);
    expect(plain).not.toMatch(/Strict-Transport-Security/);
    expect(plain).toMatch(/return 301 https:\/\/\$host\$request_uri;/);
    expect(tls).toMatch(/listen 443 ssl;/);
    expect(tls).toMatch(/Strict-Transport-Security/);
  });

  it('keeps every add_header at server level so that locations inherit the security headers', () => {
    const text = nginx.join('\n');
    const locations = [...text.matchAll(/^\s*location\s[^{]*\{([^{}]|\{[^{}]*\})*\}/gm)].map((m) => m[0]);
    expect(locations.length).toBeGreaterThan(3);
    expect(locations.filter((block) => /add_header/.test(block))).toEqual([]);
  });

  it('serves extensionless /rawdata/ files as text/plain and caches /assets/ long, HTML short', () => {
    const text = nginx.join('\n');
    expect(text).toMatch(/location \/rawdata\/ \{\s*default_type text\/plain;/);
    expect(text).toMatch(/~\^\/assets\/\s+"public, max-age=31536000, immutable";/);
    expect(text).toMatch(/default\s+"public, max-age=300";/);
    expect(text).toMatch(/add_header Cache-Control \$mwc_cache_control;/);
  });
});

describe('apache.htaccess.example', () => {
  for (const [name, value] of Object.entries(headers.all)) {
    it(`sets ${name} to the exact value`, () => {
      const matches = apache.filter((line) => new RegExp(`^\\s*Header always set ${escape(name)}\\s`).test(line));
      expect(matches).toHaveLength(1);
      expect(matches[0].trim()).toBe(`Header always set ${name} "${value}"`);
    });
  }

  it('sets Strict-Transport-Security only when the request is HTTPS', () => {
    const [[name, value]] = Object.entries(headers.httpsOnly);
    const matches = apache.filter((line) => line.includes(name));
    expect(matches).toHaveLength(1);
    expect(matches[0].trim()).toBe(`Header always set ${name} "${value}" "expr=%{HTTPS} == 'on'"`);
  });

  it('serves extensionless /rawdata/ files as text/plain and caches /assets/ long, HTML short', () => {
    const text = apache.join('\n');
    expect(text).toMatch(/<If "%\{REQUEST_URI\} =~ m#\^\/rawdata\/[^"]+">\s*ForceType "text\/plain; charset=utf-8"/);
    expect(text).toMatch(/m#\^\/assets\/#">\s*Header set Cache-Control "public, max-age=31536000, immutable"/);
    expect(text).toMatch(/<Else>\s*Header set Cache-Control "public, max-age=300"/);
  });
});

describe('_headers', () => {
  it('sets every header under /* to the exact value', () => {
    const start = netlify.indexOf('/*');
    expect(start).toBeGreaterThanOrEqual(0);
    const block: string[] = [];
    for (const line of netlify.slice(start + 1)) {
      if (!/^\s/.test(line)) break;
      block.push(line.trim());
    }
    const expected = Object.entries({ ...headers.all, ...headers.httpsOnly }).map(([name, value]) => `${name}: ${value}`);
    expect(block.sort()).toEqual(expected.sort());
  });

  it('gives /assets/* a long cache and the raw file text/plain, without a wildcard over /rawdata/', () => {
    const text = netlify.join('\n');
    expect(text).toMatch(/^\/assets\/\*\n\s+Cache-Control: public, max-age=31536000, immutable$/m);
    expect(text).toMatch(/^\/rawdata\/3hr\/benzonia\n\s+Content-Type: text\/plain; charset=utf-8$/m);
    expect(text).not.toMatch(/^\/rawdata\/.*\*/m);
  });
});

describe('legacy URL examples', () => {
  const rows = read('deploy/legacy-url-map.csv').trim().split(/\r?\n/).slice(1).map((line) => {
    const [legacy, treatment, target, status] = line.split(',');
    return { legacy, treatment, target, status };
  });
  const rebuilt = new Map(rows.filter((r) => r.status === 'rebuilt' || r.status === 'bytes-preserved').map((r) => [r.legacy, r.target]));
  const expected = [
    ['https://mawn.geo.msu.edu/station.asp?id=bnz', '/weather-network/stations/bnz/'],
    ['https://mawn.geo.msu.edu/station.asp?id=swm', '/weather-network/stations/swm/'],
    ['https://mawn.geo.msu.edu/report.asp?fileid=bnzh', '/weather-network/stations/bnz/hourly/'],
    ['https://mawn.geo.msu.edu/report.asp?fileid=bnzd', '/weather-network/stations/bnz/daily/'],
    ['https://mawn.geo.msu.edu/report.asp?fileid=bnzm', '/weather-network/stations/bnz/maintenance/'],
  ];

  it('legacy-url-map.csv lists the five example URLs as rebuilt, with these targets', () => {
    for (const [legacy, target] of expected) expect(rebuilt.get(legacy), legacy).toBe(target);
  });

  it('the nginx maps contain exactly the rebuilt station and report rows', () => {
    const text = nginx.join('\n');
    const mapBody = (variable: string) => new RegExp(`map \\$${variable} \\$\\w+ \\{([^}]*)\\}`).exec(text)![1];
    const entries = (body: string) => body.split('\n').map((l) => l.trim().replace(/;.*$/, '').split(/\s+/)).filter((p) => p.length === 2 && p[0] !== 'default');
    expect(entries(mapBody('arg_id'))).toEqual([['bnz', '/weather-network/stations/bnz/'], ['swm', '/weather-network/stations/swm/']]);
    expect(entries(mapBody('arg_fileid'))).toEqual([
      ['bnzh', '/weather-network/stations/bnz/hourly/'],
      ['bnzd', '/weather-network/stations/bnz/daily/'],
      ['bnzm', '/weather-network/stations/bnz/maintenance/'],
    ]);
    for (const [key, target] of [...entries(mapBody('arg_id')), ...entries(mapBody('arg_fileid'))]) {
      expect([...rebuilt.values()], `${key} -> ${target}`).toContain(target);
    }
    // No station that is only listed may be mapped.
    const stationIds = rows.filter((r) => /station\.asp\?id=\w+$/.test(r.legacy) && r.status === 'rebuilt').map((r) => r.legacy.split('=')[1]).sort();
    expect(stationIds).toEqual(['bnz', 'swm']);
  });

  it('the Apache rules redirect only to rebuilt paths', () => {
    const targets = apache.filter((line) => /^\s*RewriteRule /.test(line)).map((line) => line.trim().split(/\s+/)[2]);
    expect(targets).toEqual([
      '/weather-network/stations/%1/',
      '/weather-network/stations/bnz/hourly/',
      '/weather-network/stations/bnz/daily/',
      '/weather-network/stations/bnz/maintenance/',
      '/$1',
    ]);
    expect(apache.join('\n')).toMatch(/RewriteCond %\{QUERY_STRING\} \^id=\(bnz\|swm\)\$/);
  });

  it('every example names legacy-url-map.csv as the source of the full mapping and says it is an untested example', () => {
    for (const file of ['deploy/nginx.conf.example', 'deploy/apache.htaccess.example', 'deploy/_headers', 'deploy/README.md']) {
      const text = read(file);
      expect(text, file).toContain('legacy-url-map.csv');
      expect(text, file).toMatch(/EXAMPLE ONLY|untested examples/);
      expect(text, file).toMatch(/MSU IT security/);
      expect(text, file).toMatch(/institutional approval/);
    }
    expect(read('deploy/README.md')).toMatch(/Static hosting cannot rewrite query strings by itself/);
  });
});
