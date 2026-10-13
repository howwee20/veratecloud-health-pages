import swmHourly from '../../data/normalized/swm-hourly.json';
import swmDaily from '../../data/normalized/swm-daily.json';
import swmMaintenance from '../../data/normalized/swm-maintenance.json';
import { hourly, daily, maintenance, type Cell, type HourlyRow, type DailyRow } from './data';
import { runs } from './format';

/** Stations for which report data exists in the source pack. */
export const reportsByStation: Record<string, { hourly: typeof hourly; daily: typeof daily; maintenance: typeof maintenance }> = {
  bnz: { hourly, daily, maintenance },
  swm: { hourly: swmHourly as typeof hourly, daily: swmDaily as typeof daily, maintenance: swmMaintenance as typeof maintenance },
};

export const hasAnyValue = (row: { cells: Record<string, Cell> }) => Object.values(row.cells).some((c) => !c.missing);

export function latestWithValues<T extends { cells: Record<string, Cell> }>(rows: T[]): T | null {
  for (let i = rows.length - 1; i >= 0; i -= 1) if (hasAnyValue(rows[i])) return rows[i];
  return null;
}

export const hourlyLabel = (row: HourlyRow) => `${row.dateRaw} ${row.timeRaw}`;

/** Runs of consecutive rows in which every cell is a missing-value marker. */
export function emptyRuns<T extends { cells: Record<string, Cell> }>(rows: T[], label: (row: T) => string) {
  const idx = rows.map((r, i) => (hasAnyValue(r) ? -1 : i)).filter((i) => i >= 0);
  return runs(idx).map(([from, to]) => ({ from: label(rows[from]), to: label(rows[to]), count: to - from + 1 }));
}

const OFFSETS: Record<string, number> = { EDT: 4, EST: 5 };

/**
 * Minutes between an hourly row's labelled time and a UTC retrieval time.
 * Derived: relies on the report's own zone label (EDT = UTC-4, EST = UTC-5).
 */
export function minutesBefore(row: HourlyRow, zone: string, retrievedAtUtc: string): number | null {
  const offset = OFFSETS[zone];
  if (offset === undefined) return null;
  const [y, m, d] = row.isoDate.split('-').map(Number);
  const observed = Date.UTC(y, m - 1, d, row.hour + offset);
  return Math.round((new Date(retrievedAtUtc).getTime() - observed) / 60000);
}

export function duration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return [h ? `${h} h` : '', m ? `${m} min` : ''].filter(Boolean).join(' ') || '0 min';
}

export const seriesOf = (rows: (HourlyRow | DailyRow)[], key: string) => ({
  values: rows.map((r) => (typeof r.cells[key].value === 'number' ? (r.cells[key].value as number) : null)),
  raw: rows.map((r) => r.cells[key].raw),
});
