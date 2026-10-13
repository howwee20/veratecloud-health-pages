// Machine-readable companion to the /rawdata/3hr/ listing page.
import type { APIRoute } from 'astro';
import { rawdata } from '../../../lib/data';
import { preserved } from '../../../lib/raw';

const dir = rawdata.directories['3hr'];
export const GET: APIRoute = () =>
  new Response(
    JSON.stringify(
      {
        note: 'Snapshot of the legacy /rawdata/3hr/ listing. Not live. Only entries with preserved=true are stored here.',
        listingRetrievedAtUtc: dir.source.retrievedAtUtc,
        source: dir.source.url,
        entries: dir.entries.map((e: any) => {
          const file = preserved('3hr', e.name);
          return {
            name: e.name, sizeAsListed: e.sizeRaw, lastModifiedAsListed: e.lastModifiedRaw, originalUrl: e.url,
            preserved: Boolean(file), path: file ? file.localPath : null, bytes: file ? file.bytes : null, sha256: file ? file.sha256 : null,
          };
        }),
      },
      null,
      2,
    ),
    { headers: { 'Content-Type': 'application/json' } },
  );
