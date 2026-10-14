// Machine-readable companion to the /rawdata/ listing page.
import type { APIRoute } from 'astro';
import { rawdata } from '../../lib/data';

export const GET: APIRoute = () =>
  new Response(
    JSON.stringify(
      {
        note: 'Data file directory. Modification times are supplied by the directory listing.',
        listingRetrievedAtUtc: rawdata.root.source.retrievedAtUtc,
        source: rawdata.root.source.url,
        entries: rawdata.root.entries.map((e: any) => ({
          name: e.name, type: e.type, lastModifiedAsListed: e.lastModifiedRaw, originalUrl: e.url,
          listingCaptured: e.name.replace('/', '') in rawdata.directories,
        })),
      },
      null,
      2,
    ),
    { headers: { 'Content-Type': 'application/json' } },
  );
