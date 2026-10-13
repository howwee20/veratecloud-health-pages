import { describe, expect, it } from 'vitest';
import { type Cell, type HourlyRow } from '../../src/lib/data';
import hourlyFixture from '../fixtures/oct12/bnz-hourly.json';
import dailyFixture from '../fixtures/oct12/bnz-daily.json';
// Fixed October 12 edge cases; fresh release data is verified by Python and E2E integration checks.
const hourly = hourlyFixture as unknown as typeof import('../../src/lib/data').hourly;
const daily = dailyFixture as unknown as typeof import('../../src/lib/data').daily;
import { duration, emptyRuns, hasAnyValue, hourlyLabel, latestWithValues, minutesBefore, seriesOf } from '../../src/lib/station';

const value = (raw: string): Cell => ({ raw, value: Number(raw), missing: false });
const missing = (raw: '--' | '---' | 'NA'): Cell => ({ raw, value: null, missing: true });
const row = (label: string, cells: Record<string, Cell>) => ({ label, cells });

// Retrieval time of report.asp?fileid=bnzh, from manifest.csv.
const RETRIEVED = '2026-10-12T23:46:18.305422+00:00';

describe('hasAnyValue', () => {
  it('is false only when every cell is a missing marker', () => {
    expect(hasAnyValue(row('a', { x: missing('--'), y: missing('NA') }))).toBe(false);
    expect(hasAnyValue(row('b', { x: missing('--'), y: value('0.4') }))).toBe(true);
  });

  it('counts a printed zero as a value', () => {
    expect(hasAnyValue(row('c', { x: { raw: '0.00', value: 0, missing: false }, y: missing('---') }))).toBe(true);
  });
});

describe('latestWithValues', () => {
  it('returns the last row that has at least one value', () => {
    const rows = [
      row('1', { x: value('1.0') }),
      row('2', { x: value('2.0') }),
      row('3', { x: missing('--') }),
    ];
    expect(latestWithValues(rows)?.label).toBe('2');
  });

  it('returns null for no rows or for rows that are all missing', () => {
    expect(latestWithValues([])).toBeNull();
    expect(latestWithValues([row('1', { x: missing('--') }), row('2', { x: missing('NA') })])).toBeNull();
  });

  it('finds 10/12/26 18:00 in the captured hourly report', () => {
    const latest = latestWithValues(hourly.rows);
    expect(latest).not.toBeNull();
    expect(hourlyLabel(latest!)).toBe('10/12/26 18:00');
    expect(latest!.cells.airTemp.raw).toBe('74.8');
    expect(latest!.cells.precip).toEqual({ raw: '--', value: null, missing: true });
  });

  it('finds 10/03/26 in the captured daily report (10/04 to 10/11 print no values)', () => {
    const latest = latestWithValues(daily.rows);
    expect(latest?.dateRaw).toBe('10/03/26');
    expect(daily.rows[daily.rows.length - 1].dateRaw).toBe('10/11/26');
  });
});

describe('emptyRuns', () => {
  it('reports each run of all-missing rows with its first label, last label and length', () => {
    const rows = [
      row('a', { x: missing('--') }),
      row('b', { x: missing('--') }),
      row('c', { x: value('1') }),
      row('d', { x: missing('NA') }),
    ];
    expect(emptyRuns(rows, (r) => r.label)).toEqual([
      { from: 'a', to: 'b', count: 2 },
      { from: 'd', to: 'd', count: 1 },
    ]);
  });

  it('returns nothing when every row has a value', () => {
    expect(emptyRuns([row('a', { x: value('1') })], (r) => r.label)).toEqual([]);
  });

  it('matches the gaps printed in the captured hourly report', () => {
    // Read from input/mawn/report-bnzh.html: values are printed 09:00-19:00 on 10/10 and 10/11
    // and 09:00-18:00 on 10/12; every other row is "-- -- -- --- --- -- -- NA".
    const gaps = emptyRuns(hourly.rows, hourlyLabel);
    expect(gaps).toEqual([
      { from: '10/10/26 01:00', to: '10/10/26 08:00', count: 8 },
      { from: '10/10/26 20:00', to: '10/11/26 08:00', count: 13 },
      { from: '10/11/26 20:00', to: '10/12/26 08:00', count: 13 },
    ]);
    expect(gaps.reduce((n, g) => n + g.count, 0)).toBe(34);
  });

  it('matches the gaps printed in the captured daily report', () => {
    const gaps = emptyRuns(daily.rows, (r) => r.dateRaw);
    expect(gaps).toEqual([
      { from: '09/09/26', to: '09/09/26', count: 1 },
      { from: '09/15/26', to: '09/16/26', count: 2 },
      { from: '10/04/26', to: '10/11/26', count: 8 },
    ]);
  });
});

describe('minutesBefore', () => {
  const at = (isoDate: string, hour: number): HourlyRow => ({ dateRaw: '', timeRaw: '', isoDate, hour, cells: {} });

  it('reads the row time in the zone the report itself states (EDT = UTC-4)', () => {
    // 18:00 EDT is 22:00 UTC; retrieval at 23:46:18 UTC is 106.3 minutes later.
    expect(minutesBefore(at('2026-10-12', 18), 'EDT', RETRIEVED)).toBe(106);
  });

  it('uses UTC-5 for EST', () => {
    expect(minutesBefore(at('2026-10-12', 18), 'EST', RETRIEVED)).toBe(46);
  });

  it('returns null rather than guessing for an unknown zone label', () => {
    expect(minutesBefore(at('2026-10-12', 18), 'UTC', RETRIEVED)).toBeNull();
    expect(minutesBefore(at('2026-10-12', 18), '', RETRIEVED)).toBeNull();
  });

  it('treats the source label 24:00 as midnight at the end of that date', () => {
    // 10/11/26 24:00 EDT is 2026-10-12T04:00Z.
    expect(minutesBefore(at('2026-10-11', 24), 'EDT', '2026-10-12T04:00:00Z')).toBe(0);
    expect(minutesBefore(at('2026-10-11', 24), 'EDT', RETRIEVED)).toBe(1186);
  });

  it('is negative when the labelled time is after the retrieval time', () => {
    expect(minutesBefore(at('2026-10-13', 1), 'EDT', '2026-10-13T04:00:00Z')).toBe(-60);
  });

  it('gives 1 h 46 min for the latest captured hourly row', () => {
    const latest = latestWithValues(hourly.rows)!;
    const minutes = minutesBefore(latest, hourly.timezoneLabel, hourly.source.retrievedAtUtc);
    expect(hourly.timezoneLabel).toBe('EDT');
    expect(hourly.source.retrievedAtUtc).toBe(RETRIEVED);
    expect(minutes).toBe(106);
    expect(duration(minutes!)).toBe('1 h 46 min');
  });
});

describe('duration', () => {
  it('formats hours and minutes, omitting the part that is zero', () => {
    expect(duration(106)).toBe('1 h 46 min');
    expect(duration(60)).toBe('1 h');
    expect(duration(46)).toBe('46 min');
    expect(duration(0)).toBe('0 min');
  });
});

describe('seriesOf', () => {
  it('gives null, never 0, for missing cells and keeps the printed strings', () => {
    const precip = seriesOf(hourly.rows, 'precip');
    expect(precip.values).toHaveLength(66);
    // The captured hourly report prints no precipitation amount in any row.
    expect(precip.values.every((v) => v === null)).toBe(true);
    expect(new Set(precip.raw)).toEqual(new Set(['--', 'NA']));
  });

  it('keeps the 0.4 % humidity readings as numbers', () => {
    const rh = seriesOf(hourly.rows, 'relHum');
    const index = hourly.rows.findIndex((r) => r.dateRaw === '10/10/26' && r.timeRaw === '09:00');
    expect(rh.values[index]).toBe(0.4);
    expect(rh.raw[index]).toBe('0.4');
    expect(rh.values.filter((v) => v !== null)).toHaveLength(32);
    expect(rh.values).not.toContain(0);
  });

  it('has 24 daily precipitation amounts and 48 gaps', () => {
    const precip = seriesOf(daily.rows, 'precip');
    expect(precip.values.filter((v) => v !== null)).toHaveLength(24);
    expect(precip.values.filter((v) => v === null)).toHaveLength(48);
    expect(precip.values).not.toContain(0);
  });
});
