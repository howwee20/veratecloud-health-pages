import { rawdata, stationDetails, stations } from './data';

/** Raw file name -> station, only where a captured station page establishes it. */
export const stationByRawName: Record<string, { id: string; name: string; url: string }> = Object.fromEntries(
  Object.values(stationDetails)
    .filter((d: any) => d.rawFile)
    .map((d: any) => [d.rawFile.name, { id: d.id, name: stations.stations.find((s) => s.id === d.id)!.name, url: `/weather-network/stations/${d.id}/` }]),
);

export const preserved = (dir: string, name: string) => rawdata.files[`${dir}/${name}`] ?? null;

export const STATES = [
  { tone: 'ok', label: 'Preserved copy', text: 'The original bytes are stored in this prototype at the original path, with a SHA-256 checksum.' },
  { tone: 'partial', label: 'Listed in snapshot', text: 'Name, size and modification time are known from a captured directory listing. The file itself was not retrieved.' },
  { tone: 'neutral', label: 'Live source link', text: 'A link to the original server. It leaves this prototype and shows whatever the legacy system serves now.' },
  { tone: 'none', label: 'Not captured', text: 'Known only by name. Its contents and listing are not in the source pack.' },
] as const;
