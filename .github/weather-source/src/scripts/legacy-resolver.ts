// "Where would this legacy URL go?" lookup for the URL migration inventory.
// Runs entirely in the page: the mapping is bundled, nothing is fetched.
import { resolveLegacy, isLegacyHost } from '../lib/legacy';

const input = document.querySelector<HTMLInputElement>('#legacy-url');
const button = document.querySelector<HTMLButtonElement>('#legacy-url-go');
const result = document.querySelector<HTMLElement>('#legacy-url-result');

const STATUS_TEXT: Record<string, string> = {
  rebuilt: 'Rebuilt: a working page exists in this prototype.',
  'bytes-preserved': 'Preserved: the original bytes are served at the same path.',
  'template-only': 'Template only: the page template exists, but no data for this URL was captured.',
  'listed-only': 'Listed only: known from a directory listing; the file was not captured.',
  'redirect-planned': 'Would redirect to the address below. No redirect exists yet.',
  'not-preserved': 'Not preserved: nothing was captured or built for this URL.',
  superseded: 'Superseded: a legacy layout asset that the rebuild does not need.',
  'link-out': 'External: the prototype links out to this address.',
};

function line(label: string, value: string | Node): HTMLElement {
  const row = document.createElement('p');
  const strong = document.createElement('strong');
  strong.textContent = `${label}: `;
  row.append(strong, value);
  return row;
}

function show(): void {
  if (!input || !result) return;
  const value = input.value.trim();
  result.replaceChildren();
  if (!value) {
    result.append(line('Nothing entered', 'Paste a full legacy URL, for example https://mawn.geo.msu.edu/station.asp?id=bnz'));
    return;
  }
  // People paste addresses without the scheme; treat those as https.
  const address = /^[a-z][a-z0-9+.-]*:/i.test(value) ? value : `https://${value}`;
  const r = resolveLegacy(address);
  if (!r.canonical) {
    result.append(line('Not a URL', 'Enter a web address, for example https://mawn.geo.msu.edu/station.asp?id=bnz'));
    return;
  }
  const code = document.createElement('code');
  code.textContent = r.canonical;
  result.append(line('Normalised legacy URL', code));
  if (!r.known) {
    result.append(line('Result', isLegacyHost(address)
      ? 'This URL is not in the inventory. It was not referenced by any captured page, so nothing is known about it.'
      : 'This URL is not in the inventory and is not on one of the three legacy hosts.'));
    return;
  }
  result.append(line('Treatment', r.treatment ?? ''));
  result.append(line('Status in this prototype', STATUS_TEXT[r.prototypeStatus ?? ''] ?? r.prototypeStatus ?? ''));
  if (r.workingUrl) {
    const link = document.createElement('a');
    link.href = r.workingUrl;
    link.textContent = r.workingUrl;
    result.append(line('Open in the prototype', link));
  } else if (r.proposedNewUrl) {
    const proposed = document.createElement('code');
    proposed.textContent = r.proposedNewUrl;
    result.append(line('Proposed new address (not built)', proposed));
  } else {
    result.append(line('Proposed new address', 'None yet. This needs investigation or an integration.'));
  }
}

button?.addEventListener('click', show);
input?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    show();
  }
});
