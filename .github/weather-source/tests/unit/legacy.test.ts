import { describe, expect, it } from 'vitest';
import lookup from '../../data/normalized/legacy-url-lookup.json';
import { canonical, isLegacyHost, resolveLegacy } from '../../src/lib/legacy';

const MRCC = 'https://mrcc.purdue.edu/files/cliwatch/state_climatologists/michigan/prcp-7days.png';

describe('canonical', () => {
  it('upgrades http to https on the three legacy hosts', () => {
    expect(canonical('http://mawn.geo.msu.edu/station.asp?id=bnz')).toBe('https://mawn.geo.msu.edu/station.asp?id=bnz');
    expect(canonical('http://climate.geo.msu.edu/climate_maps.html')).toBe('https://climate.geo.msu.edu/climate_maps.html');
    expect(canonical('http://www.agweather.geo.msu.edu/current/')).toBe('https://www.agweather.geo.msu.edu/current/');
  });

  it('leaves an https legacy URL unchanged', () => {
    expect(canonical('https://mawn.geo.msu.edu/report.asp?fileid=bnzh')).toBe('https://mawn.geo.msu.edu/report.asp?fileid=bnzh');
  });

  it('adds the missing "www." for the agricultural weather host only', () => {
    expect(canonical('https://agweather.geo.msu.edu/forecasts/')).toBe('https://www.agweather.geo.msu.edu/forecasts/');
    expect(canonical('http://agweather.geo.msu.edu')).toBe('https://www.agweather.geo.msu.edu/');
    expect(canonical('https://mawn.geo.msu.edu/')).toBe('https://mawn.geo.msu.edu/');
  });

  it('adds the root path, lower-cases the host and trims whitespace', () => {
    expect(canonical('https://mawn.geo.msu.edu')).toBe('https://mawn.geo.msu.edu/');
    expect(canonical('HTTP://MAWN.GEO.MSU.EDU/rawdata/3hr/benzonia')).toBe('https://mawn.geo.msu.edu/rawdata/3hr/benzonia');
    expect(canonical('  https://mawn.geo.msu.edu/rawdata/  ')).toBe('https://mawn.geo.msu.edu/rawdata/');
  });

  it('keeps the query string and drops the fragment', () => {
    expect(canonical('https://mawn.geo.msu.edu/rawdata/3hr/?C=N;O=D')).toBe('https://mawn.geo.msu.edu/rawdata/3hr/?C=N;O=D');
    expect(canonical('https://mawn.geo.msu.edu/station.asp?id=bnz&rt=24')).toBe('https://mawn.geo.msu.edu/station.asp?id=bnz&rt=24');
    expect(canonical('https://climate.geo.msu.edu/climate_maps.html#top')).toBe('https://climate.geo.msu.edu/climate_maps.html');
  });

  it('does not change the scheme of hosts that are not legacy hosts', () => {
    expect(canonical('http://www.msu.edu')).toBe('http://www.msu.edu/');
    expect(canonical('http://www.cpc.ncep.noaa.gov/products/predictions/610day/')).toBe('http://www.cpc.ncep.noaa.gov/products/predictions/610day/');
  });

  it("unwraps javascript:newWindow('...') links from the climate maps page", () => {
    expect(canonical(`javascript:newWindow('${MRCC}')`)).toBe(MRCC);
    expect(canonical(`JavaScript: newWindow('http://climate.geo.msu.edu/climate_maps.html')`)).toBe('https://climate.geo.msu.edu/climate_maps.html');
  });

  it('returns null for text that is not an absolute URL', () => {
    expect(canonical('')).toBeNull();
    expect(canonical('not a url')).toBeNull();
    expect(canonical('/station.asp?id=bnz')).toBeNull();
    expect(canonical('mawn.geo.msu.edu/station.asp?id=bnz')).toBeNull();
  });

  it('is a fixed point for every key the Python pipeline wrote', () => {
    const keys = Object.keys(lookup);
    expect(keys.length).toBeGreaterThan(400);
    const changed = keys.filter((key) => canonical(key) !== key);
    expect(changed).toEqual([]);
  });
});

describe('isLegacyHost', () => {
  it('recognises the three legacy hosts and the agweather alias', () => {
    expect(isLegacyHost('https://mawn.geo.msu.edu/')).toBe(true);
    expect(isLegacyHost('http://agweather.geo.msu.edu/')).toBe(true);
    expect(isLegacyHost('https://www.agweather.geo.msu.edu/current/')).toBe(true);
    expect(isLegacyHost('https://climate.geo.msu.edu/')).toBe(true);
  });

  it('rejects other hosts and non-URLs', () => {
    expect(isLegacyHost('https://www.msu.edu/')).toBe(false);
    expect(isLegacyHost(MRCC)).toBe(false);
    expect(isLegacyHost('https://mawn.geo.msu.edu.example.org/')).toBe(false);
    expect(isLegacyHost('nonsense')).toBe(false);
  });
});

describe('resolveLegacy', () => {
  it('resolves the Benzonia station page to its rebuilt route, for http and https alike', () => {
    const expected = {
      canonical: 'https://mawn.geo.msu.edu/station.asp?id=bnz',
      known: true,
      treatment: 'REBUILD',
      proposedNewUrl: '/weather-network/stations/bnz/',
      prototypeStatus: 'rebuilt',
      pattern: 'mawn-station',
      workingUrl: '/weather-network/stations/bnz/',
    };
    expect(resolveLegacy('https://mawn.geo.msu.edu/station.asp?id=bnz')).toEqual(expected);
    expect(resolveLegacy('http://mawn.geo.msu.edu/station.asp?id=bnz')).toEqual(expected);
  });

  it('resolves the captured reports to their station sub-pages', () => {
    expect(resolveLegacy('https://mawn.geo.msu.edu/report.asp?fileid=bnzh').workingUrl).toBe('/weather-network/stations/bnz/hourly/');
    expect(resolveLegacy('https://mawn.geo.msu.edu/report.asp?fileid=bnzd').workingUrl).toBe('/weather-network/stations/bnz/daily/');
    expect(resolveLegacy('https://mawn.geo.msu.edu/report.asp?fileid=bnzm').workingUrl).toBe('/weather-network/stations/bnz/maintenance/');
  });

  it('resolves the raw file to the same path, marked bytes-preserved', () => {
    const r = resolveLegacy('http://mawn.geo.msu.edu/rawdata/3hr/benzonia');
    expect(r.canonical).toBe('https://mawn.geo.msu.edu/rawdata/3hr/benzonia');
    expect(r.known).toBe(true);
    expect(r.treatment).toBe('PRESERVE');
    expect(r.prototypeStatus).toBe('bytes-preserved');
    expect(r.workingUrl).toBe('/rawdata/3hr/benzonia');
  });

  it('resolves agweather URLs written without "www."', () => {
    const r = resolveLegacy('http://agweather.geo.msu.edu/current/');
    expect(r.canonical).toBe('https://www.agweather.geo.msu.edu/current/');
    expect(r.workingUrl).toBe('/agricultural-weather/current/');
    expect(resolveLegacy('agweather.geo.msu.edu/current/').known).toBe(false);
  });

  it('knows a listed-only station but offers no working URL for it', () => {
    const r = resolveLegacy('https://mawn.geo.msu.edu/station.asp?id=aet');
    expect(r.known).toBe(true);
    expect(r.treatment).toBe('REBUILD');
    expect(r.proposedNewUrl).toBe('/weather-network/stations/aet/');
    expect(r.prototypeStatus).toBe('template-only');
    expect(r.workingUrl).toBeNull();
  });

  it('knows a raw file that was only listed but does not claim it is preserved', () => {
    const r = resolveLegacy('https://mawn.geo.msu.edu/rawdata/3hr/aetna');
    expect(r.known).toBe(true);
    expect(r.prototypeStatus).toBe('listed-only');
    expect(r.proposedNewUrl).toBe('/rawdata/3hr/aetna');
    expect(r.workingUrl).toBeNull();
  });

  it('offers no new URL for dynamic products that were not captured', () => {
    for (const url of [
      'https://mawn.geo.msu.edu/station.asp?id=bnz&rt=24',
      'https://www.agweather.geo.msu.edu/forecasts/fcst.asp?fileid=fpus63kgrr',
    ]) {
      const r = resolveLegacy(url);
      expect(r.known).toBe(true);
      expect(r.treatment).toBe('NEEDS INVESTIGATION');
      expect(r.proposedNewUrl).toBeNull();
      expect(r.workingUrl).toBeNull();
    }
  });

  it('treats planned redirects as planned, not working', () => {
    const r = resolveLegacy('https://climate.geo.msu.edu/index.html');
    expect(r.treatment).toBe('REDIRECT');
    expect(r.proposedNewUrl).toBe('/climate/');
    expect(r.prototypeStatus).toBe('redirect-planned');
    expect(r.workingUrl).toBeNull();
  });

  it("resolves a javascript:newWindow('...') map link as an external dependency", () => {
    const r = resolveLegacy(`javascript:newWindow('${MRCC}')`);
    expect(r.canonical).toBe(MRCC);
    expect(r.known).toBe(true);
    expect(r.treatment).toBe('EXTERNAL DEPENDENCY');
    expect(r.pattern).toBe('external-mrcc-map');
    expect(r.workingUrl).toBeNull();
  });

  it('reports an unknown URL on a legacy host as unknown, with every field null', () => {
    expect(resolveLegacy('https://mawn.geo.msu.edu/station.asp?id=zzz')).toEqual({
      canonical: 'https://mawn.geo.msu.edu/station.asp?id=zzz',
      known: false,
      treatment: null,
      proposedNewUrl: null,
      prototypeStatus: null,
      pattern: null,
      workingUrl: null,
    });
    expect(resolveLegacy('https://example.org/').known).toBe(false);
  });

  it('reports unparseable input as unknown without throwing', () => {
    expect(resolveLegacy('not a url')).toEqual({
      canonical: null,
      known: false,
      treatment: null,
      proposedNewUrl: null,
      prototypeStatus: null,
      pattern: null,
      workingUrl: null,
    });
    expect(resolveLegacy('').known).toBe(false);
  });

  it('only ever returns a working URL for entries marked rebuilt or bytes-preserved', () => {
    const table = lookup as Record<string, { t: string; n: string | null; s: string; p: string }>;
    const working = Object.keys(table).filter((key) => resolveLegacy(key).workingUrl !== null);
    expect(working.length).toBe(14); // the 14 captured URLs, and nothing else
    for (const key of working) {
      expect(['rebuilt', 'bytes-preserved']).toContain(table[key].s);
      expect(resolveLegacy(key).workingUrl).toBe(table[key].n);
      expect(table[key].n).toMatch(/^\//);
    }
  });
});
