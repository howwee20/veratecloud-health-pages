// Re-derives displayed values straight from the captured HTML with a plain
// regular expression (no Python, no HTML parser) and compares them with the
// frozen October 12 regression fixtures. Current release JSON and CSVs are independently
// checked against the active source pack by tests/python/test_parsers.py.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const read = (relative: string) => {
 const fixture = relative.startsWith('data/normalized/') || relative.startsWith('public/downloads/') || relative === 'public/rawdata/3hr/benzonia';
 return readFileSync(`${ROOT}${fixture ? 'tests/fixtures/oct12/' + relative.split('/').pop() : relative}`);
};
const PACK = 'data/source-snapshots/weather-source-pack/';
const MARKERS = ['--', '---', 'NA'];
const ZERO = /^-?0+(\.0+)?$/;

interface Cell { raw: string; value: number | string | null; missing: boolean }
interface Row { dateRaw: string; timeRaw?: string; isoDate: string; cells: Record<string, Cell> }
interface Report { source: { sha256: string; url: string }; columns: { key: string; type: string }[]; rows: Row[]; timezoneLabel?: string }

/** The report block as printed: one line of &nbsp; and <br> inside td.courier2. */
function reportText(relative: string): string {
  const html = read(PACK + relative).toString('latin1');
  const blocks = [...html.matchAll(/<td class="courier2">([\s\S]*?)<\/td>/g)];
  expect(blocks).toHaveLength(1);
  const block = blocks[0][1].trim();
  expect(block).not.toContain('\n');
  expect(new Set(block.match(/&\w+;/g))).toEqual(new Set(['&nbsp;']));
  expect(new Set(block.match(/<[^>]+>/g))).toEqual(new Set(['<br>']));
  return block.replaceAll('<br>', '\n').replaceAll('&nbsp;', ' ');
}

/** Data rows only: lines that begin with MM/DD/YY, split on runs of spaces. */
function dataRows(relative: string): string[][] {
  return reportText(relative)
    .split('\n')
    .filter((line) => /^\d{2}\/\d{2}\/\d{2}\s/.test(line))
    .map((line) => line.trim().split(/\s+/));
}

function manifest(): Record<string, { bytes: number; sha256: string }> {
  const lines = read(`${PACK}manifest.csv`).toString('utf8').trim().split(/\r?\n/).slice(1);
  return Object.fromEntries(
    lines.map((line) => {
      const [, file, , bytes, sha256] = line.split(',');
      return [file, { bytes: Number(bytes), sha256 }];
    }),
  );
}

const sha256 = (data: Buffer) => createHash('sha256').update(data).digest('hex');
const json = <T>(name: string) => JSON.parse(read(`data/normalized/${name}`).toString('utf8')) as T;
const csv = (name: string) =>
  read(`public/downloads/${name}`).toString('utf8').split(/\r?\n/).filter((line) => line !== '').map((line) => line.split(','));

describe('bnz-hourly.json against input/mawn/report-bnzh.html', () => {
  const source = dataRows('input/mawn/report-bnzh.html');
  const hourly = json<Report>('bnz-hourly.json');

  it('was built from the file the manifest describes', () => {
    const entry = manifest()['input/mawn/report-bnzh.html'];
    const bytes = read(`${PACK}input/mawn/report-bnzh.html`);
    expect(bytes.length).toBe(entry.bytes);
    expect(sha256(bytes)).toBe(entry.sha256);
    expect(hourly.source.sha256).toBe(entry.sha256);
  });

  it('has the 66 rows the page prints, in the same order, cell for cell', () => {
    expect(source).toHaveLength(66);
    expect(hourly.rows).toHaveLength(66);
    const keys = hourly.columns.map((c) => c.key);
    expect(keys).toHaveLength(8);
    const got = hourly.rows.map((r) => [r.dateRaw, r.timeRaw, ...keys.map((k) => r.cells[k].raw)]);
    expect(got).toEqual(source);
  });

  it('takes its time-zone label from the page', () => {
    const labels = new Set([...reportText('input/mawn/report-bnzh.html').matchAll(/Date\s+\((\w+)\)/g)].map((m) => m[1]));
    expect([...labels]).toEqual(['EDT']);
    expect(hourly.timezoneLabel).toBe('EDT');
  });

  it('shows the latest observation exactly as printed: 74.8, 62.2, 68.4, DRY, SW, 2.9, 17.6 and no precipitation value', () => {
    const lastWithValue = [...source].reverse().find((tokens) => tokens.slice(2).some((t) => !MARKERS.includes(t)))!;
    expect(lastWithValue).toEqual(['10/12/26', '18:00', '74.8', '62.2', '68.4', 'DRY', 'SW', '2.9', '17.6', '--']);
    const row = hourly.rows.find((r) => r.dateRaw === '10/12/26' && r.timeRaw === '18:00')!;
    expect(row.cells.airTemp).toEqual({ raw: '74.8', value: 74.8, missing: false });
    expect(row.cells.relHum).toEqual({ raw: '62.2', value: 62.2, missing: false });
    expect(row.cells.soilTemp).toEqual({ raw: '68.4', value: 68.4, missing: false });
    expect(row.cells.windDir).toEqual({ raw: 'SW', value: 'SW', missing: false });
    expect(row.cells.windSpeed).toEqual({ raw: '2.9', value: 2.9, missing: false });
    expect(row.cells.solarRad).toEqual({ raw: '17.6', value: 17.6, missing: false });
    expect(row.cells.precip).toEqual({ raw: '--', value: null, missing: true });
  });

  it('stores null for every missing marker and a matching number for everything else', () => {
    let markers = 0;
    for (const row of hourly.rows) {
      for (const column of hourly.columns) {
        const cell = row.cells[column.key];
        if (MARKERS.includes(cell.raw)) {
          markers += 1;
          expect(cell).toEqual({ raw: cell.raw, value: null, missing: true });
        } else if (column.type === 'number') {
          expect(cell.missing).toBe(false);
          expect(cell.value).toBe(Number(cell.raw));
        } else {
          expect(cell).toEqual({ raw: cell.raw, value: cell.raw, missing: false });
        }
      }
    }
    expect(markers).toBe(source.flatMap((tokens) => tokens.slice(2)).filter((t) => MARKERS.includes(t)).length);
    expect(markers).toBe(315);
  });

  it('contains no zero, because the page prints none', () => {
    expect(source.flatMap((tokens) => tokens.slice(2)).filter((t) => ZERO.test(t))).toEqual([]);
    const values = hourly.rows.flatMap((r) => Object.values(r.cells).map((c) => c.value));
    expect(values.filter((v) => v === 0)).toEqual([]);
  });

  it('keeps the 0.4 % humidity readings of 10/10/26', () => {
    const printed = source.filter((t) => t[0] === '10/10/26' && t[3] === '0.4').map((t) => t[1]);
    expect(printed).toEqual(['09:00', '10:00', '11:00', '12:00', '19:00']);
    const stored = hourly.rows.filter((r) => r.dateRaw === '10/10/26' && r.cells.relHum.value === 0.4).map((r) => r.timeRaw);
    expect(stored).toEqual(printed);
  });
});

describe('bnz-daily.json against input/mawn/report-bnzd.html', () => {
  const source = dataRows('input/mawn/report-bnzd.html');
  const daily = json<Report>('bnz-daily.json');

  it('was built from the file the manifest describes', () => {
    const entry = manifest()['input/mawn/report-bnzd.html'];
    expect(sha256(read(`${PACK}input/mawn/report-bnzd.html`))).toBe(entry.sha256);
    expect(daily.source.sha256).toBe(entry.sha256);
  });

  it('has the 72 rows the page prints, cell for cell', () => {
    expect(source).toHaveLength(72);
    const keys = daily.columns.map((c) => c.key);
    expect(keys).toHaveLength(9);
    expect(daily.rows.map((r) => [r.dateRaw, ...keys.map((k) => r.cells[k].raw)])).toEqual(source);
    expect(source[0][0]).toBe('08/01/26');
    expect(source[71][0]).toBe('10/11/26');
  });

  it('keeps partial rows partial: 09/30/26 has no air minimum, 10/03/26 has no air temperatures, precipitation or PET', () => {
    expect(source.find((t) => t[0] === '09/30/26')).toEqual(['09/30/26', '67.8', '--', '64.5', '61.4', '0.44', '94.4', '49.4', '83.4', '0.026']);
    expect(source.find((t) => t[0] === '10/03/26')).toEqual(['10/03/26', '--', '--', '63.6', '53.4', '--', '0.4', '35.1', '342.3', '---']);
    const sep30 = daily.rows.find((r) => r.dateRaw === '09/30/26')!;
    expect(sep30.cells.airMin).toEqual({ raw: '--', value: null, missing: true });
    expect(sep30.cells.airMax.value).toBe(67.8);
    const oct3 = daily.rows.find((r) => r.dateRaw === '10/03/26')!;
    expect(Object.entries(oct3.cells).filter(([, c]) => c.missing).map(([k]) => k)).toEqual(['airMax', 'airMin', 'precip', 'pet']);
    expect(oct3.cells.relHum.value).toBe(0.4);
  });

  it('never turns a missing precipitation cell into 0', () => {
    const index = 1 + daily.columns.findIndex((c) => c.key === 'precip');
    expect(index).toBe(5);
    const printedAmounts = source.filter((t) => !MARKERS.includes(t[index]));
    expect(printedAmounts).toHaveLength(24);
    expect(printedAmounts.filter((t) => ZERO.test(t[index]))).toEqual([]);
    const stored = daily.rows.map((r) => r.cells.precip);
    expect(stored.filter((c) => c.value === null)).toHaveLength(48);
    expect(stored.filter((c) => c.value === 0)).toEqual([]);
    expect(stored.filter((c) => c.missing).every((c) => c.value === null)).toBe(true);
  });
});

describe('published CSV downloads', () => {
  it('benzonia-hourly.csv has a header and 66 rows holding the printed strings', () => {
    const rows = csv('benzonia-hourly.csv');
    expect(rows).toHaveLength(67);
    expect(rows[0][0]).toBe('date');
    expect(rows[0][1]).toBe('time_EDT_as_labelled');
    expect(rows[0]).toHaveLength(10);
    expect(rows.slice(1)).toEqual(dataRows('input/mawn/report-bnzh.html'));
  });

  it('benzonia-hourly.csv keeps "--", "---" and "NA" cells and has no fabricated zeros', () => {
    const cells = csv('benzonia-hourly.csv').slice(1).flatMap((r) => r.slice(2));
    expect(cells).toHaveLength(528);
    expect(cells.filter((c) => c === '--')).toHaveLength(213);
    expect(cells.filter((c) => c === '---')).toHaveLength(68);
    expect(cells.filter((c) => c === 'NA')).toHaveLength(34);
    expect(cells.filter((c) => c === '')).toEqual([]);
    expect(cells.filter((c) => ZERO.test(c))).toEqual([]);
    // The last column (precipitation) holds a marker in every row of this capture.
    expect(new Set(csv('benzonia-hourly.csv').slice(1).map((r) => r[9]))).toEqual(new Set(['--', 'NA']));
  });

  it('benzonia-daily.csv has a header and 72 rows holding the printed strings', () => {
    const rows = csv('benzonia-daily.csv');
    expect(rows).toHaveLength(73);
    expect(rows[0][0]).toBe('date');
    expect(rows[0]).toHaveLength(10);
    expect(rows.slice(1)).toEqual(dataRows('input/mawn/report-bnzd.html'));
    const cells = rows.slice(1).flatMap((r) => r.slice(1));
    expect(cells.filter((c) => c === '--')).toHaveLength(101);
    expect(cells.filter((c) => c === '---')).toHaveLength(42);
    expect(cells.filter((c) => c === 'NA')).toHaveLength(11);
    expect(cells.filter((c) => c === '' || ZERO.test(c))).toEqual([]);
  });

  it('the raw logger file under public/ is the pack file, byte for byte', () => {
    const entry = manifest()['input/rawdata/3hr/benzonia'];
    const published = read('public/rawdata/3hr/benzonia');
    expect(published.equals(read(`${PACK}input/rawdata/3hr/benzonia`))).toBe(true);
    expect(published.length).toBe(2001);
    expect(sha256(published)).toBe(entry.sha256);
  });
});
