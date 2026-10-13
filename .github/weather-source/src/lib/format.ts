const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-10-12T23:46:18.305422+00:00" -> "12 Oct 2026, 23:46 UTC" */
export function fmtUtc(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`;
}

export function shortSha(sha: string): string {
  return `${sha.slice(0, 12)}…`;
}

export function fmtBytes(n: number): string {
  return `${n.toLocaleString('en-US')} bytes`;
}

export function pct(part: number, whole: number): string {
  if (!whole) return '0%';
  const value = (part / whole) * 100;
  return `${value < 10 && value > 0 ? value.toFixed(1) : Math.round(value)}%`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`;
}

/** Collapse consecutive indexes into [from, to] runs. */
export function runs(indexes: number[]): [number, number][] {
  const out: [number, number][] = [];
  for (const i of indexes) {
    const last = out[out.length - 1];
    if (last && last[1] === i - 1) last[1] = i;
    else out.push([i, i]);
  }
  return out;
}

export const MISSING_TEXT: Record<string, string> = {
  '--': 'No value reported (source shows --)',
  '---': 'No value reported (source shows ---)',
  NA: 'Not available (source shows NA)',
};
