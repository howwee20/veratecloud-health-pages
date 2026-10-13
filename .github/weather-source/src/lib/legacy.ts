import lookup from '../../data/normalized/legacy-url-lookup.json';

type Entry = { t: string; n: string | null; s: string; p: string };
const table = lookup as Record<string, Entry>;

const CANONICAL_HOST: Record<string, string> = {
  'mawn.geo.msu.edu': 'mawn.geo.msu.edu',
  'www.agweather.geo.msu.edu': 'www.agweather.geo.msu.edu',
  'agweather.geo.msu.edu': 'www.agweather.geo.msu.edu',
  'climate.geo.msu.edu': 'climate.geo.msu.edu',
};

/** Same normalisation as scripts/pipeline/inventory.py:canonical. */
export function canonical(input: string): string | null {
  const js = /^javascript:\s*newWindow\('([^']+)'\)/i.exec(input.trim());
  let url: URL;
  try {
    url = new URL(js ? js[1] : input.trim());
  } catch {
    return null;
  }
  const host = url.hostname.toLowerCase();
  const legacy = CANONICAL_HOST[host];
  const scheme = legacy ? 'https' : url.protocol.replace(':', '');
  return `${scheme}://${legacy ?? host}${url.pathname || '/'}${url.search}`;
}

export function isLegacyHost(input: string): boolean {
  try {
    return new URL(input).hostname.toLowerCase() in CANONICAL_HOST;
  } catch {
    return false;
  }
}

export interface Resolution {
  canonical: string | null;
  known: boolean;
  treatment: string | null;
  proposedNewUrl: string | null;
  prototypeStatus: string | null;
  pattern: string | null;
  /** A page or file that actually exists in this prototype, or null. */
  workingUrl: string | null;
}

const WORKING = new Set(['rebuilt', 'bytes-preserved']);

export function resolveLegacy(input: string): Resolution {
  const key = canonical(input);
  const entry = key ? table[key] : undefined;
  return {
    canonical: key,
    known: Boolean(entry),
    treatment: entry?.t ?? null,
    proposedNewUrl: entry?.n ?? null,
    prototypeStatus: entry?.s ?? null,
    pattern: entry?.p ?? null,
    workingUrl: entry && WORKING.has(entry.s) ? entry.n : null,
  };
}
