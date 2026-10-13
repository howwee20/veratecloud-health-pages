// Shared by the two climate pages so that anchors on /climate/ always match
// the ids on /climate/maps/. The leading underscore keeps this file out of routing.
import { climate } from '../../lib/data';

export type MapKind = 'precipitation' | 'temperature' | 'other';

export interface ClimateMap {
  period: string; sourceAlt: string; imageUrl: string; imageHost: string;
  declaredWidth: string | null; declaredHeight: string | null;
}
export interface MapGroup { title: string; id: string; kind: MapKind; maps: ClimateMap[] }

const slug = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** Precipitation or temperature, decided from the group title printed by the source. */
export const kindOf = (title: string): MapKind => (/precip/i.test(title) ? 'precipitation' : /temp/i.test(title) ? 'temperature' : 'other');

export const KIND_LABEL: Record<MapKind, string> = {
  precipitation: 'Precipitation',
  temperature: 'Temperature',
  other: 'Other',
};

export const mapGroups: MapGroup[] = (climate.maps.groups as { title: string; maps: ClimateMap[] }[]).map((group) => ({
  title: group.title,
  id: `map-${slug(group.title)}`,
  kind: kindOf(group.title),
  maps: group.maps,
}));

export const groupsOf = (kind: MapKind) => mapGroups.filter((g) => g.kind === kind);
export const mapCount = mapGroups.reduce((n, g) => n + g.maps.length, 0);
export const MAPS_URL = '/climate/maps/';
