export interface DocumentAlternative {
  sourceSha256: string;
  title: string;
  html: string;
  status: 'full' | 'partial';
}

const files = import.meta.glob('../../data/document-alternatives/*.json', {
  eager: true,
  import: 'default',
}) as Record<string, DocumentAlternative>;

export function documentAlternative(page: {download?: string; source?: {sha256: string}}) {
  const id = page.download?.split('/').pop()?.split('.')[0];
  const alternative = id && files[`../../data/document-alternatives/${id}.json`];
  if (!alternative) return undefined;
  // Historical source changes require rechecking the corresponding transcription.
  if (alternative.sourceSha256 !== page.source?.sha256) {
    throw new Error(`Document ${id} changed; verify its HTML alternative before publishing.`);
  }
  return alternative;
}
