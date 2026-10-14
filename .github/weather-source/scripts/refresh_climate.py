"""Refresh the 27 named MRCC climate maps and their matching text together.

Never publishes an image with yesterday's description. Provider layout, period,
legend labels and regional samples must validate before any public file changes.
Run after build_data.py: python scripts/refresh_climate.py --execute
Requires tesseract on PATH; --from-directory revalidates previously fetched PNGs.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import httpx
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parent.parent
REFERENCES = ROOT / 'data/climate-map-references.json'
DESCRIPTIONS = ROOT / 'data/normalized/map-descriptions.json'
RECEIPTS = ROOT / 'public/downloads/climate-map-refresh.json'
# Samples are inside Michigan, in the fixed provider map projection. They are
# deliberately regional visual samples, never represented as station values,
# full-region extrema, averages, or the provider's underlying gridded dataset.
REGIONS = {
    'Western Upper Peninsula': [(240, 472), (280, 460), (310, 480), (335, 465)],
    'Central Upper Peninsula': [(380, 500), (420, 510), (460, 505), (485, 495)],
    'Eastern Upper Peninsula': [(535, 485), (570, 485), (595, 510), (625, 522)],
    'Northern Lower Peninsula': [(605, 650), (650, 665), (690, 680), (605, 715), (670, 725)],
    'Central Lower Peninsula': [(540, 790), (595, 800), (650, 790), (595, 850), (660, 865)],
    'Thumb': [(775, 825), (795, 875), (795, 920)],
    'Southern Lower Peninsula': [(545, 945), (600, 960), (660, 960), (715, 990), (580, 1030), (660, 1040)],
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def transcribe_image(image: Image.Image, *, psm: int = 6) -> str:
    """OCR transcription only; this is not a complete text equivalent of a map."""
    with tempfile.TemporaryDirectory(prefix='weather-ocr-') as temp:
        path = Path(temp) / 'image.png'
        image.save(path)
        result = subprocess.run(['tesseract', str(path), 'stdout', '--psm', str(psm)],
                                capture_output=True, text=True, timeout=30, check=True)
        return result.stdout.strip()


def legend_ticks(image: Image.Image) -> list[int]:
    pixels = [x for x in range(50, 885) if max(image.getpixel((x, 1230))) < 50]
    clusters: list[list[int]] = []
    for x in pixels:
        if not clusters or x > clusters[-1][-1] + 1:
            clusters.append([])
        clusters[-1].append(x)
    ticks = [round(sum(v) / len(v)) for v in clusters]
    if not 3 <= len(ticks) <= 20 or abs(ticks[0] - 68) > 2 or abs(ticks[-1] - 862) > 2:
        raise ValueError('Unrecognized provider legend geometry')
    return ticks


def legend_values(image: Image.Image, refs: dict) -> tuple[list[float], list[int]]:
    ticks = legend_ticks(image)
    fingerprint = digest(image.crop(tuple(refs['legendCrop'])).tobytes())
    if fingerprint in refs['knownLegends']:
        values = refs['knownLegends'][fingerprint]
    else:
        # Numeric glyph recognition against manually checked source labels.
        # Unknown or ambiguous labels fail closed rather than guessing a scale.
        values = []
        half = min(40, (ticks[1] - ticks[0]) // 2)
        for x in ticks:
            ink = image.crop((x-half, 1240, x+half+1, 1300)).convert('L').point(lambda p: 255 if p < 128 else 0)
            box = ink.getbbox()
            if box is None:
                raise ValueError('Missing numeric legend label')
            cropped = ink.crop(box)
            ratio = cropped.width / cropped.height
            normalized = cropped.resize((40, 40), Image.Resampling.NEAREST)
            scores = {}
            for template in refs['labels']:
                if abs(ratio - template['aspect']) > .09:
                    continue
                reference = Image.frombytes('L', (40, 40), base64.b64decode(template['pixels']))
                score = ImageStat.Stat(ImageChops.difference(normalized, reference)).mean[0] / 255
                value = template['value']
                scores[value] = min(scores.get(value, 1), score)
            ranked = sorted(scores.items(), key=lambda item: item[1])
            if not ranked or ranked[0][1] > .045 or (len(ranked) > 1 and ranked[1][1] - ranked[0][1] < .025):
                raise ValueError('Unrecognized or ambiguous numeric legend label')
            values.append(ranked[0][0])
    if len(values) != len(ticks) or any(a >= b for a, b in zip(values, values[1:])):
        raise ValueError('Legend labels are not strictly increasing')
    return values, ticks


def numeric_range(lower: float, upper: float) -> str:
    return f'{lower:g} to {upper:g}'


def regional_samples(image: Image.Image, values: list[float], ticks: list[int]) -> list[dict]:
    palette: dict[tuple[int, int, int], list[int]] = {}
    for i, (left, right) in enumerate(zip(ticks, ticks[1:])):
        palette.setdefault(image.getpixel(((left+right)//2, 1200)), []).append(i)
    if any(max(color) < 40 for color in palette):
        raise ValueError('Unexpected black legend band')
    output = []
    for region, points in REGIONS.items():
        counts: Counter = Counter()
        total = 0
        for x, y in points:
            for px in range(x-8, x+9):
                for py in range(y-8, y+9):
                    total += 1
                    color = image.getpixel((px, py))
                    if color in palette:
                        counts[tuple(palette[color])] += 1
        if sum(counts.values()) / total < .70:
            raise ValueError(f'Insufficient recognized map colors in {region}')
        # Repeated white legend bands are combined; their sign cannot be inferred.
        bands = []
        for indices, count in counts.most_common():
            bands.append({'lower': values[min(indices)], 'upper': values[max(indices)+1],
                          'range': numeric_range(values[min(indices)], values[max(indices)+1]),
                          'samplePixels': count})
        output.append({'region': region, 'dominantRange': bands[0]['range'],
                       'sampledRanges': ', '.join(b['range'] for b in sorted(bands, key=lambda b:b['lower'])),
                       'bands': bands, 'recognizedPixels': sum(counts.values()), 'sampledPixels': total})
    return output


def describe(raw: bytes, name: str, group: dict, map_item: dict, receipt: dict, refs: dict) -> dict:
    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Response is not a PNG')
    image = Image.open(io.BytesIO(raw)).convert('RGB')
    if image.size != (932, 1400):
        raise ValueError(f'Provider map dimensions changed: {image.size}')
    # Layout anchors prevent sampling shifted maps with plausible-looking colors.
    for point in [(70, 202), (500, 202), (862, 300)]:
        if max(image.getpixel(point)) > 80:
            raise ValueError('Provider map frame changed')
    header = transcribe_image(image.crop((40, 140, 890, 196)))
    date_match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4}) to ([A-Z][a-z]+ \d{1,2}, \d{4})', header)
    if not date_match:
        raise ValueError(f'Cannot validate map period: {header}')
    start, end = [datetime.strptime(value, '%B %d, %Y').date() for value in date_match.groups()]
    expected_days = int(re.search(r'(7|30|90)days', name).group(1))
    if (end - start).days + 1 != expected_days:
        raise ValueError('Map period does not match its named product')
    footer = transcribe_image(image.crop((40, 1300, 890, 1398)))
    generated_match = re.search(r'Generated on:\s*(.+)', footer)
    if not generated_match or 'PRISM Weather Data' not in footer:
        raise ValueError(f'Cannot validate provider date/data source: {footer}')
    generated = generated_match.group(1).strip()
    generated_date = datetime.strptime(re.sub(r'\s+(EDT|EST)$', '', generated), '%a %b %d, %Y %H:%M:%S').date()
    if generated_date < end or (generated_date - end).days > 7:
        raise ValueError('Provider generated date disagrees with period')
    values, ticks = legend_values(image, refs)
    regions = regional_samples(image, values, ticks)
    unit = 'percent of normal' if name.startswith('prcpdev2') else ('inches' if name.startswith('prcp') else 'degrees F')
    return {'period': f'{start.strftime("%B %-d, %Y")} to {end.strftime("%B %-d, %Y")}',
            'periodStart': start.isoformat(), 'periodEnd': end.isoformat(),
            'summary': ' '.join(f'{r["region"]}: the most frequent sampled color represents {r["dominantRange"]} {unit}.' for r in regions),
            'legend': values, 'unit': unit, 'regions': regions,
            'basis': 'Approximate color-band samples from seven Michigan regions in this exact map image. These are not station measurements, regional averages, or full-region minima and maxima. Shared colors span multiple legend intervals; those intervals are combined. The underlying gridded numbers are not supplied with the image.',
            'provider': 'Midwestern Regional Climate Center', 'dataSource': 'PRISM Weather Data',
            'sourceUrl': map_item['imageUrl'], 'title': group['title'], 'generated': generated,
            'checkedAtUtc': receipt['checkedAt'], 'sourceLastModified': receipt.get('lastModified'),
            'sha256': digest(raw), 'descriptionMethod': 'validated legend and regional raster samples v1'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--from-directory', type=Path)
    args = parser.parse_args()
    if not args.execute and not args.from_directory:
        parser.error('Use --execute for the authorized read-only refresh, or --from-directory for offline validation')
    groups = json.loads((ROOT/'data/normalized/climate.json').read_text())['maps']['groups']
    refs = json.loads(REFERENCES.read_text())
    staged, descriptions, receipts = {}, {}, []
    previous = json.loads(RECEIPTS.read_text()) if RECEIPTS.exists() else {}
    previous_descriptions = json.loads(DESCRIPTIONS.read_text()) if DESCRIPTIONS.exists() else {}
    prior = {r['name']: r for r in previous.get('maps', [])}
    offline_receipts = {}
    if args.from_directory:
        offline_receipts = {r['name']:r for r in json.loads((args.from_directory/'receipts.json').read_text())}
    with httpx.Client(timeout=45, follow_redirects=False, headers={'User-Agent':'VerateCloud-Weather-Demo/1.0 (authorized bounded read-only refresh)'}) as client:
        for group in groups:
            for item in group['maps']:
                if not re.fullmatch(r'https://mrcc\.purdue\.edu/files/cliwatch/state_climatologists/michigan/(?:prcp|prcpdev|prcpdev2|tmax|tmaxdev|tmean|tmeandev|tmin|tmindev)-(?:7|30|90)days\.png', item['imageUrl']):
                    raise ValueError('Map URL is outside the 27 authorized provider products')
                name = item['imageUrl'].split('/')[-1]
                if args.from_directory:
                    raw = (args.from_directory/name).read_bytes()
                    receipt = dict(offline_receipts[name])
                    if receipt['sha256'] != digest(raw) or receipt['url'] != item['imageUrl']:
                        raise ValueError('Offline image receipt does not match source')
                else:
                    time.sleep(2)
                    headers = {}
                    if prior.get(name, {}).get('lastModified'):
                        headers['If-Modified-Since'] = prior[name]['lastModified']
                    response = client.get(item['imageUrl'], headers=headers)
                    if response.status_code == 304:
                        raw = (ROOT/'public/media/climate'/name).read_bytes()
                        if digest(raw) != prior[name]['sha256']:
                            raise ValueError('Cached map SHA does not match last successful receipt')
                    else:
                        response.raise_for_status()
                        if response.status_code != 200 or len(response.content) > 5_000_000:
                            raise ValueError('Unexpected source response')
                        raw = response.content
                    receipt = {'name':name, 'url':item['imageUrl'], 'status':response.status_code,
                               'checkedAt':datetime.now(timezone.utc).isoformat(), 'sha256':digest(raw),
                               'lastModified':response.headers.get('last-modified') or prior.get(name, {}).get('lastModified')}
                descriptions[name] = describe(raw, name, group, item, receipt, refs)
                previous_end = previous_descriptions.get(name, {}).get('periodEnd')
                if previous_end and descriptions[name]['periodEnd'] < previous_end:
                    raise ValueError('Provider returned an older map than the published version')
                staged[name] = raw
                receipts.append(receipt)
                print(f'Validated {name}: {descriptions[name]["period"]}', flush=True)
    if len(staged) != 27:
        raise ValueError(f'Expected 27 maps; got {len(staged)}')
    # All image+description pairs validated before touching the served assets.
    for name, raw in staged.items():
        (ROOT/'public/media/climate'/name).write_bytes(raw)
    DESCRIPTIONS.write_text(json.dumps(descriptions, indent=2)+'\n')
    RECEIPTS.parent.mkdir(exist_ok=True)
    RECEIPTS.write_text(json.dumps({'lastSuccessfulRefreshUtc':max(r['checkedAt'] for r in receipts),
                                   'mapCount':27, 'method':'Bounded conditional GET; image and matching text validated before publication',
                                   'maps':receipts}, indent=2)+'\n')
    with (ROOT/'public/downloads/climate-map-regional-samples.csv').open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['map','period_start','period_end','region','lower_bound','upper_bound','unit','sample_pixels','image_sha256'])
        for name, d in descriptions.items():
            for region in d['regions']:
                for band in region['bands']:
                    writer.writerow([name,d['periodStart'],d['periodEnd'],region['region'],band['lower'],band['upper'],d['unit'],band['samplePixels'],d['sha256']])
    print('Published 27 matching map/text pairs and their source receipts.')


if __name__ == '__main__':
    main()
