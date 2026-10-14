import {stationDetails} from './data';
import {reportsByStation} from './station';

export const dailyTemperatures = Object.entries(stationDetails).map(([id, station]) => {
  const report = reportsByStation[id]?.daily;
  const row = report?.rows.reduce<(typeof report.rows)[number] | undefined>(
    (latest, candidate) => !latest || candidate.isoDate > latest.isoDate ? candidate : latest, undefined,
  );
  return {
    id,
    station: `${station.city} (${station.stationName})`,
    date: row?.isoDate || 'Unavailable',
    maximum: row?.cells.airMax?.raw || 'Unavailable',
    minimum: row?.cells.airMin?.raw || 'Unavailable',
  };
}).sort((a,b) => a.station.localeCompare(b.station));

export const temperatureCsv = [
  ['Station', 'Station ID', 'Observation date', 'Maximum air temperature (F)', 'Minimum air temperature (F)'],
  ...dailyTemperatures.map(row => [row.station, row.id, row.date, row.maximum, row.minimum]),
].map(row => row.map(cell => `"${cell.replaceAll('"','""')}"`).join(',')).join('\r\n')+'\r\n';
