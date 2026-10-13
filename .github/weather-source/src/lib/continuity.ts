// Service-continuity model. Statuses and wording are authored here; every
// number is computed from the inventory, the normalized data or the test
// evidence, never typed in.
// evidence.json is written by "npm run evidence". The site still builds without
// it (first run, or after a clean), showing "not yet generated" where relevant.
const evidenceFiles = import.meta.glob('../../data/normalized/evidence.json', { eager: true, import: 'default' });
const zero = { pages: 0, pagesWithViolations: 0, violationRules: 0, violationNodes: 0, byImpact: { critical: 0, serious: 0, moderate: 0, minor: 0 } };
const evidenceJson = Object.values(evidenceFiles)[0] ?? {
  missing: true, generatedAtUtc: null, tools: {}, build: null,
  rules: { wcagTags: [], styleDependentRulesExcludedForLegacy: [] },
  legacy: { method: '', testedLive: false, pages: [], totals: zero },
  modern: { method: '', pages: [], totals: { desktop: zero, mobile: zero, structuralSubsetDesktop: zero }, pagesWithConsoleProblems: [], pagesWithFailedRequests: [], pagesWithExternalRequests: [], pagesWithOverflowAt320: [] },
  notTested: [],
};
import { inventory, inventoryRecords, stations, hourly, daily, maintenance, rawdata, sources, agweather, climate } from './data';
import type { Tone } from '../components/StatusBadge.astro';

export const evidence = evidenceJson as unknown as any;

export type SiteId = 'mawn' | 'agweather' | 'climate';
export type Status = 'preserved' | 'partial' | 'integration' | 'none';

export const STATUS: Record<Status, { label: string; tone: Tone; meaning: string }> = {
  preserved: { label: 'Preserved in prototype', tone: 'ok', meaning: 'Works in this prototype from captured content. Still a snapshot on a laptop, not a production service.' },
  partial: { label: 'Partially preserved', tone: 'partial', meaning: 'The capability works for the captured subset only, or works without something the original had.' },
  integration: { label: 'Requires integration', tone: 'needs', meaning: 'Cannot be static. Needs an approved data feed, API or backend that this prototype does not have.' },
  none: { label: 'Not yet preserved', tone: 'none', meaning: 'Known to exist from links only. Nothing was captured and nothing was built.' },
};

const pattern = (id: string) => inventory.patterns.find((p: any) => p.patternId === id) ?? { urlCount: 0, capturedCount: 0 };
const n = (id: string) => pattern(id).urlCount as number;
const cap = (id: string) => pattern(id).capturedCount as number;
const countLinks = (page: any) => page.sections.reduce((a: number, s: any) => a + s.groups.reduce((b: number, g: any) => b + g.links.length, 0), 0);
const mapCount = climate.maps.groups.reduce((a: number, g: any) => a + g.maps.length, 0);
const threeHr = rawdata.directories['3hr'].entries.length;
const preservedFiles = Object.keys(rawdata.files).length;

export interface Feature {
  site: SiteId;
  name: string;
  status: Status;
  evidence: string;
  needs: string;
  href?: string;
  dependsOn?: string;
}

export const features: Feature[] = [
  // ---- MAWN ---------------------------------------------------------------
  { site: 'mawn', name: 'Station directory', status: 'preserved', href: '/weather-network/',
    evidence: `All ${stations.counts.total} stations listed on the legacy home page, with IDs, groups and ${stations.counts.retired} retirement dates, in a searchable table.`,
    needs: 'A maintained station list from the data owners, so additions and retirements appear without a re-capture.', dependsOn: 'Station metadata held by the legacy server' },
  { site: 'mawn', name: 'Station map picker', status: 'partial', href: '/weather-network/#map-h',
    evidence: `Hotspot positions for ${stations.stations.filter((s) => s.imageMapPixel).length} stations are plotted. The map image and the two regional zoom pages were not captured.`,
    needs: 'Coordinates for every station and an approved base map, with the table kept as the primary way to choose a station.' },
  { site: 'mawn', name: 'Station pages', status: 'partial', href: '/weather-network/stations/bnz/',
    evidence: `${cap('mawn-station')} of ${n('mawn-station')} station pages rebuilt from captured pages using one shared template.`,
    needs: `Station details for the other ${n('mawn-station') - cap('mawn-station')} stations.`, dependsOn: 'Station database behind station.asp' },
  { site: 'mawn', name: 'Hourly reports', status: 'partial', href: '/weather-network/stations/bnz/hourly/',
    evidence: `1 station (Benzonia): ${hourly.stats.rowCount} hourly rows as an accessible table with charts and CSV. Fixed at capture time.`,
    needs: 'A scheduled, approved export of each station\'s hourly report or its underlying data.', dependsOn: 'Report generator behind report.asp' },
  { site: 'mawn', name: 'Daily reports', status: 'partial', href: '/weather-network/stations/bnz/daily/',
    evidence: `1 station (Benzonia): ${daily.stats.rowCount} daily rows with a date-range filter, charts and CSV. Fixed at capture time.`,
    needs: 'The same scheduled export as hourly reports.', dependsOn: 'Report generator behind report.asp' },
  { site: 'mawn', name: 'Maintenance records', status: 'partial', href: '/weather-network/stations/bnz/maintenance/',
    evidence: `1 station (Benzonia): ${maintenance.entryCount} entries, searchable, with the original text retained.`,
    needs: 'Station notes for the other stations; these change rarely and suit periodic static generation.' },
  { site: 'mawn', name: 'Recent conditions on the home page', status: 'integration', href: '/weather-network/#recent-h',
    evidence: 'The values printed on the legacy home page at capture are shown as a labelled snapshot.',
    needs: 'A live observation feed. A stored reading must never be presented as current.', dependsOn: 'Live station data feed' },
  { site: 'mawn', name: 'Custom reports (data on demand)', status: 'integration',
    evidence: `${n('mawn-custom-report')} custom-report URLs seen across ${cap('mawn-station')} captured station pages (daily, hourly, five-minute, growing degree-day). None exercised.`,
    needs: 'A query API or approved backend over the observation database. This cannot be pre-generated for arbitrary date ranges.', dependsOn: 'Observation database and ASP query code' },
  { site: 'mawn', name: 'Raw-data directory listings', status: 'partial', href: '/rawdata/',
    evidence: `Root listing and 1 of ${rawdata.root.entries.length} subdirectory listings (3hr, ${threeHr} files) rebuilt at the original paths, with a JSON index.`,
    needs: `Listings for the other ${rawdata.root.entries.length - 1} subdirectories and a decision on keeping an Apache-style index for scripts.` },
  { site: 'mawn', name: 'Raw data files', status: 'partial', href: '/rawdata/3hr/',
    evidence: `${preservedFiles} of ${threeHr} files in 3hr preserved byte for byte at its original path, with a SHA-256 checksum.`,
    needs: 'A scheduled, approved copy of the raw files. The listing shows them changing within the hour.', dependsOn: 'Logger collection system writing /rawdata/' },
  { site: 'mawn', name: 'Station photographs', status: 'none',
    evidence: `${n('mawn-station-photo')} photo URLs referenced by the captured station pages. None captured.`,
    needs: 'Approved copies of the images and a text alternative for each.' },
  { site: 'mawn', name: 'Regional zoom maps', status: 'none',
    evidence: `${n('mawn-regional-map')} pages linked from the home-page map. Not captured.`, needs: 'Capture and review of the pages.' },

  // ---- Agricultural Weather -----------------------------------------------
  { site: 'agweather', name: 'Office home, news and contact details', status: 'preserved', href: '/agricultural-weather/',
    evidence: `Support statement, contact details, ${agweather.home.news.length} news items and ${agweather.home.recentAdditions.length} recent station additions from the captured home page.`,
    needs: 'An owner and a way to publish news without a re-capture.' },
  { site: 'agweather', name: 'Current-weather product directory', status: 'preserved', href: '/agricultural-weather/current/',
    evidence: `${countLinks(agweather.current)} products in ${agweather.current.sections.length} sections, searchable, each labelled by how it would have to be delivered.`,
    needs: 'Nothing for the directory itself. The products behind it are separate rows below.' },
  { site: 'agweather', name: 'Forecast product directory', status: 'preserved', href: '/agricultural-weather/forecasts/',
    evidence: `${countLinks(agweather.forecasts)} products in ${agweather.forecasts.sections.length} sections, searchable. No forecast text is stored.`,
    needs: 'Nothing for the directory itself.' },
  { site: 'agweather', name: 'Observation, statistics and summary text products', status: 'integration',
    evidence: `${n('agweather-current-report')} report.asp products linked. None captured.`,
    needs: 'Confirmation of where each product comes from, then either a link to the authoritative provider or an approved feed.', dependsOn: 'Data feed reported on the legacy page as "LDM"; product source unverified' },
  { site: 'agweather', name: 'Forecast text products', status: 'integration',
    evidence: `${n('agweather-forecast-product')} fcst.asp products linked. None captured, and none should be cached.`,
    needs: 'Live delivery from the authoritative provider. Forecasts are time-critical.', dependsOn: 'Data feed reported on the legacy page as "LDM"; product source unverified' },
  { site: 'agweather', name: 'Daily temperature and growing-degree-day normals', status: 'none',
    evidence: `${n('agweather-normals')} normal.asp pages linked. None captured.`,
    needs: 'Capture of the tables. If they are fixed climatological normals they suit static generation; unverified.' },
  { site: 'agweather', name: 'Data-feed status indicator', status: 'integration', href: '/agricultural-weather/',
    evidence: `The legacy page printed "${agweather.home.datafeedStatusRaw.join('", "')}" at capture; shown as a snapshot.`,
    needs: 'Real monitoring of whichever feeds a production service depends on.' },
  { site: 'agweather', name: 'Outlook links to NOAA Climate Prediction Center', status: 'preserved', href: '/agricultural-weather/forecasts/',
    evidence: `${n('external-noaa-cpc')} links to the external provider, kept as links.`, needs: 'Periodic link checking.', dependsOn: 'NOAA Climate Prediction Center' },
  { site: 'agweather', name: 'Information, feature articles and other-sites sections', status: 'none',
    evidence: `${n('agweather-section-index')} section indexes linked from the navigation. None captured.`, needs: 'Capture and content review.' },
  { site: 'agweather', name: 'Temperature graphics and station-list pages', status: 'none',
    evidence: `${n('agweather-static-page')} pages linked. None captured.`, needs: 'Capture; graphics would need text alternatives.' },

  // ---- Climate -------------------------------------------------------------
  { site: 'climate', name: 'Office home and navigation', status: 'preserved', href: '/climate/',
    evidence: 'Welcome text, partner links and navigation from the captured home page.', needs: 'An owner for content updates.' },
  { site: 'climate', name: 'Climate map directory', status: 'partial', href: '/climate/maps/',
    evidence: `${mapCount} maps in ${climate.maps.groups.length} groups listed with links to the images. Images are hosted externally and not embedded.`,
    needs: 'Permission or an agreed feed for the images, plus a text or table equivalent for each map. None exists in the captured pages.', dependsOn: 'Midwestern Regional Climate Center image files' },
  { site: 'climate', name: 'Climate statistics: normals and historical summary tables', status: 'none',
    evidence: 'Linked as climate_mi/index.html. Not captured.', needs: 'Capture of the map-linked summary tables; likely the most valuable static content on this site.' },
  { site: 'climate', name: 'SEMCOG precipitation data', status: 'none',
    evidence: 'Linked as semcog/sem/mainsem.html. Not captured.', needs: 'Capture and confirmation of ownership and currency.' },
  { site: 'climate', name: 'About the office', status: 'none', evidence: 'Linked as about_us.html. Not captured.', needs: 'Capture.' },
];

const SOURCE_IDS: Record<SiteId, string[]> = {
  mawn: sources.sources.filter((s) => s.id.startsWith('mawn-') || s.id.startsWith('rawdata-')).map((s) => s.id),
  agweather: sources.sources.filter((s) => s.id.startsWith('agweather-')).map((s) => s.id),
  climate: sources.sources.filter((s) => s.id.startsWith('climate-')).map((s) => s.id),
};
const ROUTE_PREFIX: Record<SiteId, string[]> = {
  mawn: ['/weather-network/', '/rawdata/', '/rawdata-inspect/'],
  agweather: ['/agricultural-weather/'],
  climate: ['/climate/'],
};

export interface SiteModel {
  id: SiteId; name: string; host: string; home: string; purpose: string;
  inv: any; features: Feature[]; byStatus: Record<Status, number>;
  capturedBytes: number; capturedResponses: number; archived: string[];
  externalHosts: { host: string; urls: number }[];
  routes: any[]; legacyPages: any[];
  a11y: { routes: number; desktopRules: number; mobileRules: number; legacyRules: number; legacyPages: number };
  blockers: string[];
}

function buildSite(id: SiteId, name: string, host: string, home: string, purpose: string, archived: string[], blockers: string[]): SiteModel {
  const own = features.filter((f) => f.site === id);
  const byStatus = { preserved: 0, partial: 0, integration: 0, none: 0 } as Record<Status, number>;
  own.forEach((f) => (byStatus[f.status] += 1));
  const srcs = sources.sources.filter((s) => SOURCE_IDS[id].includes(s.id));
  const pageUrls = new Set(srcs.map((s) => s.url));
  const hosts = new Map<string, number>();
  for (const r of inventoryRecords) {
    if (r.site === 'external' && r.discoveredOn.some((u: string) => pageUrls.has(u))) hosts.set(r.host, (hosts.get(r.host) ?? 0) + 1);
  }
  const routes = evidence.modern.pages.filter((p: any) => ROUTE_PREFIX[id].some((prefix) => p.route.startsWith(prefix)));
  const legacyPages = evidence.legacy.pages.filter((p: any) => SOURCE_IDS[id].includes(p.sourceId));
  return {
    id, name, host, home, purpose, inv: inventory.sites[id], features: own, byStatus,
    capturedBytes: srcs.reduce((a, s) => a + s.bytes, 0), capturedResponses: srcs.length, archived,
    externalHosts: [...hosts.entries()].map(([h, urls]) => ({ host: h, urls })).sort((a, b) => b.urls - a.urls),
    routes, legacyPages,
    a11y: {
      routes: routes.length,
      desktopRules: routes.reduce((a: number, p: any) => a + p.viewports.desktop.axe.violationRules, 0),
      mobileRules: routes.reduce((a: number, p: any) => a + p.viewports.mobile.axe.violationRules, 0),
      legacyRules: legacyPages.reduce((a: number, p: any) => a + p.axe.violationRules, 0),
      legacyPages: legacyPages.length,
    },
    blockers,
  };
}

export const sites: SiteModel[] = [
  buildSite('mawn', 'Michigan Automated Weather Network (MAWN)', 'mawn.geo.msu.edu', '/weather-network/',
    'Station-by-station weather data for the Enviro-weather network: station pages, pre-generated hourly and daily reports, maintenance notes, custom reports and a public raw-data directory.',
    [`${hourly.stats.rowCount} hourly rows, ${daily.stats.rowCount} daily rows and ${maintenance.entryCount} maintenance entries for Benzonia`, `Station details for ${SOURCE_IDS.mawn.filter((s) => s.startsWith("mawn-station")).length} stations`, `${preservedFiles} raw file (${rawdata.files['3hr/benzonia'].bytes.toLocaleString('en-US')} bytes), byte-identical`, `Listings for /rawdata/ and /rawdata/3hr/ (${threeHr} files)`],
    [
      'No approved data feed: reports and raw files here are frozen at capture time.',
      `${n('mawn-station') - cap('mawn-station')} of ${n('mawn-station')} stations have no captured data.`,
      'Custom reports need a query backend that does not exist outside the legacy server.',
      'Raw-file schema is undocumented; a data dictionary is needed from the maintainers.',
      'robots.txt disallows automated access; wider capture needs maintainer authorization or a server-side export.',
    ]),
  buildSite('agweather', 'MSU Agricultural Weather Office', 'www.agweather.geo.msu.edu', '/agricultural-weather/',
    'A directory of current-weather, statistics, growing-degree-day and forecast products for Michigan agriculture, with office news and contact details.',
    ['Home page content, news and station additions', `Directories of ${countLinks(agweather.current)} current-weather and ${countLinks(agweather.forecasts)} forecast products`, 'No product bodies'],
    [
      `None of the ${n('agweather-current-report') + n('agweather-forecast-product') + n('agweather-normals')} linked reports was captured, so their sources and formats are unverified.`,
      'Forecast products must be delivered live from an authoritative provider; a decision is needed on linking versus relaying.',
      'Three navigation sections (information, feature articles, other sites) were not captured.',
    ]),
  buildSite('climate', "Michigan State Climatologist's Office", 'climate.geo.msu.edu', '/climate/',
    'Historical climate information for Michigan: Climate Watch maps for 7, 30 and 90 days, climate statistics and normals, and SEMCOG precipitation data.',
    ['Home page text and navigation', `Directory of ${mapCount} map products (links only)`, 'No statistics tables'],
    [
      `All ${mapCount} map images are hosted by a third party and have no text or table equivalent in the captured pages.`,
      'The historical climate statistics tables, probably the core content, were not captured.',
      'The legacy footer says the page was last updated in 2009; content currency needs an owner\'s review.',
    ]),
];

export const sharedBlockers = [
  { title: 'No institutional approval', text: 'This is an independent prototype. Replacing or redirecting any legacy URL needs a decision by the service owners and approval for DNS, routing and hosting changes.' },
  { title: 'Capture scope is 14 responses', text: 'All three hosts disallow automated access in robots.txt. Only the 14 URLs named in the brief were retrieved, once each. Everything else is known from links.' },
  { title: 'No data pipeline', text: 'Nothing refreshes. A production service needs scheduled, approved exports from the systems that produce the reports and raw files.' },
  { title: 'Accessibility not manually tested', text: 'The rebuilt pages have been checked with automated tools only. No keyboard, zoom or screen-reader testing has been performed by a person. Conformance is not established.' },
  { title: 'Security not reviewed', text: 'The institutional scan findings were not provided. A static frontend removes some attack surface in principle; whether it satisfies MSU requirements is for MSU IT security to decide.' },
  { title: 'Hosting and ownership undecided', text: 'No approved hosting environment, monitoring, incident process or maintenance owner has been identified.' },
];

export const totals = {
  inventoryUrls: inventory.totalUrls as number,
  legacyHostUrls: inventory.legacyHostUrls as number,
  externalUrls: inventory.externalUrls as number,
  captured: inventory.capturedUrls as number,
  patterns: inventory.patterns.length as number,
  capturedBytes: sources.sources.reduce((a, s) => a + s.bytes, 0),
  rebuiltLegacyUrls: (inventory.byPrototypeStatus.rebuilt ?? 0) + (inventory.byPrototypeStatus['bytes-preserved'] ?? 0),
  routes: evidence.modern.pages.length as number,
  features: features.length,
  byStatus: features.reduce((acc, f) => ({ ...acc, [f.status]: (acc[f.status] ?? 0) + 1 }), {} as Record<Status, number>),
};

// ---- comparison notes, one per captured legacy page -------------------------
export interface CompareNote { title: string; preserved: string[]; changed: string[]; unresolved: string[] }

const reportChanged = [
  'Fixed-width text built from non-breaking spaces becomes a data table with a caption, column headers and row headers.',
  'Missing-value markers are kept and announced to screen readers as "no value reported".',
  'Charts with table equivalents, a filter limited to the captured dates, and a CSV download.',
  'Source URL, retrieval time and checksum on the page.',
];

export const compareNotes: Record<string, CompareNote> = {
  'mawn-home': {
    title: 'MAWN home page',
    preserved: [`All ${stations.counts.total} station names, IDs and groups`, `${stations.counts.retired} retirement dates`, 'Introductory text and partner links', 'Recent-conditions values as printed'],
    changed: ['Clickable image map replaced by a searchable, filterable table that works by keyboard', 'Layout tables replaced by headings, landmarks and a data table', 'Each station shows whether data for it exists in the prototype'],
    unresolved: ['Map image and two regional zoom pages', 'Live recent conditions', `${n('mawn-station') - cap('mawn-station')} station pages`],
  },
  'mawn-station-bnz': {
    title: 'Benzonia station page',
    preserved: ['Station name, ID, location, city, latitude, longitude and elevation as printed', 'Links to hourly, daily and maintenance reports', 'The four custom-report types, listed'],
    changed: ['One page now shows identity, the latest reported observation, charts, recent rows, maintenance and downloads', 'Explicit notice of data gaps and of what is a snapshot', 'Responsive layout down to 320px, visible focus, skip link'],
    unresolved: ['Custom reports (need a data backend)', 'Station photograph', 'Automatic refresh'],
  },
  'mawn-station-swm': {
    title: 'SWMREC station page',
    preserved: ['Station name, ID, location, city, latitude, longitude and elevation as printed', 'The four custom-report types, listed'],
    changed: ['Same template as Benzonia', 'States plainly that reports and the raw file were not captured, instead of showing placeholders'],
    unresolved: ['Hourly, daily and maintenance reports', 'Raw file', 'Custom reports', 'Station photograph'],
  },
  'mawn-report-bnzh': {
    title: 'Benzonia hourly report',
    preserved: [`All ${hourly.stats.rowCount} rows and ${hourly.stats.cellCount} cells, character for character`, `${hourly.stats.missingCellCount} missing-value markers kept as markers`, `Time-zone label "${hourly.timezoneLabel}" as given`, `${hourly.footnotes.length} source footnotes`],
    changed: reportChanged,
    unresolved: ['Refresh from the legacy report generator', 'Reports for other stations', 'Meaning of the -- and NA markers is not defined by the source'],
  },
  'mawn-report-bnzd': {
    title: 'Benzonia daily report',
    preserved: [`All ${daily.stats.rowCount} rows and ${daily.stats.cellCount} cells, character for character`, `${daily.stats.missingCellCount} missing-value markers kept as markers`, `${daily.footnotes.length} source footnotes`],
    changed: reportChanged,
    unresolved: ['Refresh from the legacy report generator', 'Dates outside the captured report (need custom reports)', 'Accumulation window for daily totals is not stated by the source'],
  },
  'mawn-report-bnzm': {
    title: 'Benzonia maintenance report',
    preserved: [`${maintenance.entryCount} dated entries with their wording`, 'The complete original text, available on the page and as a download', `${maintenance.entriesWithPartialDate} partial dates shown as written`],
    changed: ['Entries presented as a table with search and a year filter', 'Shared indentation removed from entry text; line breaks kept'],
    unresolved: ['New entries after capture', 'Notes for other stations'],
  },
  'rawdata-index': {
    title: 'Raw-data directory root',
    preserved: [`${rawdata.root.entries.length} subdirectory names and modification times as listed`, 'The /rawdata/ path itself'],
    changed: ['Server-generated listing replaced by a table that says what is and is not held', 'Machine-readable JSON index added'],
    unresolved: [`${rawdata.root.entries.length - 1} subdirectories known by name only`, 'Sort-order query links', 'Apache-format listing for scripts that parse it'],
  },
  'rawdata-3hr-index': {
    title: 'Raw-data 3hr directory',
    preserved: [`${threeHr} file names, sizes and modification times as listed`, `${preservedFiles} file stored byte for byte at its original path`],
    changed: ['Searchable table with station links where they can be verified', 'Checksums and capture times shown', 'Machine-readable JSON index added'],
    unresolved: [`${threeHr - preservedFiles} files not captured`, 'No refresh', 'Raw-file schema not established'],
  },
  'agweather-home': {
    title: 'Agricultural Weather Office home',
    preserved: ['Support statement and contact details', `${agweather.home.news.length} news items and ${agweather.home.recentAdditions.length} recent additions`, 'Navigation categories'],
    changed: ['Navigation shows which sections exist in the prototype', 'Data-feed status labelled as a snapshot rather than a live indicator'],
    unresolved: ['Information, feature articles and other-sites sections', 'Live feed status'],
  },
  'agweather-current': {
    title: 'Current weather products',
    preserved: [`${countLinks(agweather.current)} product links in ${agweather.current.sections.length} sections, with source labels`],
    changed: ['Products are searchable', 'Each product is labelled: requires integration, not captured, or external provider'],
    unresolved: ['Every product body: none was captured'],
  },
  'agweather-forecasts': {
    title: 'Forecast products',
    preserved: [`${countLinks(agweather.forecasts)} product links in ${agweather.forecasts.sections.length} sections, with source labels`],
    changed: ['Products are searchable and labelled by delivery type', 'States that no forecast is stored or shown'],
    unresolved: ['Every forecast: must come live from the authoritative provider'],
  },
  'climate-home': {
    title: "State Climatologist's Office home",
    preserved: ['Welcome text and partner links', 'Navigation entries', 'The page\'s own "last updated" statement'],
    changed: ['Navigation shows which resources exist in the prototype', 'External map thumbnails are not embedded'],
    unresolved: ['About, SEMCOG data and climate-statistics pages'],
  },
  'climate-climate_maps': {
    title: 'Michigan climate maps',
    preserved: [`${mapCount} map products in ${climate.maps.groups.length} groups, with periods and the source's own short descriptions`, 'Units statement'],
    changed: ['Maps listed as a structured directory instead of 27 hot-linked images', 'javascript: pop-up links replaced by ordinary links'],
    unresolved: [`Text or table equivalents for ${mapCount} maps`, 'Permission or feed for the images', 'Which maps are current'],
  },
};
