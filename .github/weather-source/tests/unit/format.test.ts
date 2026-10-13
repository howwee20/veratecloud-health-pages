import { describe, expect, it } from 'vitest';
import { MISSING_TEXT, fmtBytes, fmtUtc, pct, plural, runs, shortSha } from '../../src/lib/format';

describe('runs', () => {
  it('collapses consecutive indexes into inclusive [from, to] pairs', () => {
    expect(runs([0, 1, 2, 5, 7, 8])).toEqual([[0, 2], [5, 5], [7, 8]]);
  });

  it('returns nothing for no indexes and a single pair for one index', () => {
    expect(runs([])).toEqual([]);
    expect(runs([3])).toEqual([[3, 3]]);
  });

  it('keeps a full range as one run and does not modify its input', () => {
    const input = [4, 5, 6, 7];
    expect(runs(input)).toEqual([[4, 7]]);
    expect(input).toEqual([4, 5, 6, 7]);
  });

  it('does not merge indexes that are not adjacent', () => {
    expect(runs([1, 3, 5])).toEqual([[1, 1], [3, 3], [5, 5]]);
  });
});

describe('fmtUtc', () => {
  it('formats the manifest timestamp of the hourly report in UTC', () => {
    // retrieved_at_utc for report.asp?fileid=bnzh in manifest.csv
    expect(fmtUtc('2026-10-12T23:46:18.305422+00:00')).toBe('12 Oct 2026, 23:46 UTC');
  });

  it('converts other offsets to UTC rather than printing local time', () => {
    expect(fmtUtc('2026-10-12T19:46:18-04:00')).toBe('12 Oct 2026, 23:46 UTC');
    expect(fmtUtc('2026-10-13T01:05:00+02:00')).toBe('12 Oct 2026, 23:05 UTC');
  });

  it('zero-pads hours and minutes but not the day', () => {
    expect(fmtUtc('2026-01-05T04:07:00Z')).toBe('5 Jan 2026, 04:07 UTC');
    expect(fmtUtc('2025-12-31T00:00:00Z')).toBe('31 Dec 2025, 00:00 UTC');
  });
});

describe('pct', () => {
  it('rounds to a whole percent at 10 % and above', () => {
    expect(pct(34, 66)).toBe('52%');
    expect(pct(1, 3)).toBe('33%');
    expect(pct(10, 10)).toBe('100%');
    expect(pct(1, 10)).toBe('10%');
  });

  it('keeps one decimal below 10 % so that a small share is not shown as 0 %', () => {
    expect(pct(1, 119)).toBe('0.8%');
    expect(pct(2, 119)).toBe('1.7%');
    expect(pct(14, 437)).toBe('3.2%');
  });

  it('returns 0% for a zero part and for an empty whole instead of NaN', () => {
    expect(pct(0, 10)).toBe('0%');
    expect(pct(0, 0)).toBe('0%');
    expect(pct(5, 0)).toBe('0%');
  });
});

describe('plural', () => {
  it('uses the singular only for exactly one', () => {
    expect(plural(1, 'row')).toBe('1 row');
    expect(plural(0, 'row')).toBe('0 rows');
    expect(plural(66, 'row')).toBe('66 rows');
  });

  it('accepts an irregular plural', () => {
    expect(plural(52, 'entry', 'entries')).toBe('52 entries');
    expect(plural(1, 'entry', 'entries')).toBe('1 entry');
  });

  it('groups thousands', () => {
    expect(plural(1234, 'URL')).toBe('1,234 URLs');
  });
});

describe('small formatters', () => {
  it('fmtBytes groups thousands (the raw file is 2,001 bytes)', () => {
    expect(fmtBytes(2001)).toBe('2,001 bytes');
  });

  it('shortSha keeps the first 12 characters and marks the cut', () => {
    expect(shortSha('71a6597b052ff77b12d17f9ec82f18a11214a35bc2e3402dbda9f78d9c150c9b')).toBe('71a6597b052f…');
  });

  it('describes each of the three source markers as missing, never as zero', () => {
    expect(Object.keys(MISSING_TEXT).sort()).toEqual(['--', '---', 'NA']);
    for (const text of Object.values(MISSING_TEXT)) {
      expect(text).not.toMatch(/\b0\b|zero/i);
      expect(text).toMatch(/No value reported|Not available/);
    }
  });
});
