// Machine-readable companion to the /rawdata/3hr/ listing page.
import type { APIRoute } from 'astro';
import { rawdata } from '../../../lib/data';
import network from '../../../../data/expanded/network.json';
import {statSync} from 'node:fs';

const dir = rawdata.directories['3hr'];
export const GET: APIRoute = () =>
  new Response(
    JSON.stringify(
      {
        note: 'Three-hour data file directory. Modification times are supplied by the directory listing.',
        listingRetrievedAtUtc: dir.source.retrievedAtUtc,
        source: dir.source.url,
        entries: dir.entries.map((e: any) => {
          const file = (network.rawFiles as Record<string, any>)[e.url];
          return {
            name: e.name, sizeAsListed: e.sizeRaw, lastModifiedAsListed: e.lastModifiedRaw, originalUrl: e.url,
            preserved: Boolean(file), path: file ? file.path : null, bytes: file ? statSync('public'+file.path).size : null, sha256: file ? file.source.sha256 : null,
          };
        }),
      },
      null,
      2,
    ),
    { headers: { 'Content-Type': 'application/json' } },
  );
