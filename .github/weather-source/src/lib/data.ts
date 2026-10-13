// Typed access to the versioned, normalized data produced by scripts/build_data.py.
import stationsJson from '../../data/normalized/stations.json';
import detailsJson from '../../data/normalized/station-details.json';
import hourlyJson from '../../data/normalized/bnz-hourly.json';
import dailyJson from '../../data/normalized/bnz-daily.json';
import maintenanceJson from '../../data/normalized/bnz-maintenance.json';
import networkHomeJson from '../../data/normalized/network-home.json';
import rawdataJson from '../../data/normalized/rawdata.json';
import crosscheckJson from '../../data/normalized/raw-crosscheck.json';
import agweatherJson from '../../data/normalized/agweather.json';
import climateJson from '../../data/normalized/climate.json';
import sourcesJson from '../../data/normalized/sources.json';
import inventorySummaryJson from '../../data/normalized/inventory-summary.json';
import inventoryRecordsJson from '../../data/normalized/inventory-records.json';

export interface SourceRef { id: string; url: string; file: string; sha256: string; retrievedAtUtc: string }
export interface Cell { raw: string; value: number | string | null; missing: boolean }
export interface Column { key: string; label: string; short?: string; unit: string | null; sourceHeader: string; type: 'number' | 'text' }
export interface HourlyRow { dateRaw: string; timeRaw: string; isoDate: string; hour: number; cells: Record<string, Cell> }
export interface DailyRow { dateRaw: string; isoDate: string; cells: Record<string, Cell> }
export interface Seg { text: string; url: string | null }

export interface Station {
  id: string; name: string; listedAs: string; group: 'michigan' | 'tower-10m' | 'tower-20m' | 'retired';
  sourceGroupHeading: string; retiredDateRaw: string | null; towerHeightRaw: string | null; legacyUrl: string;
  onLegacyImageMap: boolean; imageMapLabel: string | null; imageMapPixel: [number, number] | null;
  capture: { stationPage: boolean; hourly: boolean; daily: boolean; maintenance: boolean; rawFile: boolean };
  captureLevel: 'full' | 'metadata' | 'listed'; city: string | null; prototypeUrl: string | null;
}

export const stations = stationsJson as unknown as { source: SourceRef; counts: Record<string, number>; captureCounts: Record<string, number>; stations: Station[] };
export const stationDetails = detailsJson.stations as unknown as Record<string, any>;
export const hourly = hourlyJson as unknown as {
  source: SourceRef; timezoneLabel: string; location: string[]; columns: Column[]; days: string[]; rows: HourlyRow[];
  footnotes: string[]; stats: any; parsing: { method: string; transformations: string[]; missingValues: string };
};
export const daily = dailyJson as unknown as {
  source: SourceRef; location: string[]; columns: Column[]; months: string[]; rows: DailyRow[];
  footnotes: string[]; stats: any; parsing: { method: string; transformations: string[]; missingValues: string };
};
export const maintenance = maintenanceJson as unknown as {
  source: SourceRef; title: string; entryCount: number; entriesWithPartialDate: number; firstIsoDate: string; lastIsoDate: string; rawText: string;
  entries: { dateRaw: string; isoDate: string | null; heading: string | null; bracketCode: string | null; section: number; body: string[] }[];
};
export const networkHome = networkHomeJson as unknown as {
  source: SourceRef; intro: Seg[][]; stationPickerInstruction: string[]; regionalMapLinks: { label: string; url: string }[];
  imageMapAreaCount: number; imageMapSize: [number, number]; recentConditions: { headingRaw: string; items: { label: string; raw: string }[] };
};
export const rawdata = rawdataJson as unknown as any;
export const crosscheck = crosscheckJson as unknown as any;
export const agweather = agweatherJson as unknown as any;
export const climate = climateJson as unknown as any;
export const sources = sourcesJson as unknown as { pack: Record<string, string>; sources: any[]; observedResponseHeaders: { note: string; responses: number; present: Record<string, number> } };
export const inventory = inventorySummaryJson as unknown as any;
export const inventoryRecords = (inventoryRecordsJson as unknown as { records: any[] }).records;

export const sourceById = (id: string) => sources.sources.find((s) => s.id === id);

export const GROUP_LABEL: Record<Station['group'], string> = {
  michigan: 'Michigan station',
  'tower-10m': 'Tower station, 10 m',
  'tower-20m': 'Tower station, 20 m',
  retired: 'Retired station',
};
