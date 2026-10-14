"""Climate refresh refuses stale descriptions and unrecognized provider images."""
import importlib.util
import io
import json
from pathlib import Path
import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('climate_refresh',ROOT/'scripts/refresh_climate.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
REFS=json.loads(C.REFERENCES.read_text())

@pytest.mark.parametrize('name', ['prcp-7days.png','prcp-90days.png','prcpdev-7days.png','prcpdev2-30days.png','tmax-7days.png','tmindev-30days.png'])
def test_current_map_legend_and_regions(name):
    image=Image.open(ROOT/'public/media/climate'/name).convert('RGB')
    values,ticks=C.legend_values(image,REFS)
    assert len(values)==len(ticks)
    assert all(a<b for a,b in zip(values,values[1:]))
    regions=C.regional_samples(image,values,ticks)
    assert len(regions)==7
    assert all(r['recognizedPixels']/r['sampledPixels']>=.7 for r in regions)


def test_white_bands_are_combined_without_inventing_sign():
    image=Image.open(ROOT/'public/media/climate/prcpdev-7days.png').convert('RGB')
    values,ticks=C.legend_values(image,REFS)
    regions=C.regional_samples(image,values,ticks)
    assert any(b['lower']==-1 and b['upper']==1 for r in regions for b in r['bands'])


def test_unknown_layout_rejected():
    image=Image.new('RGB',(932,1400),'white')
    with pytest.raises(ValueError,match='geometry'): C.legend_values(image,REFS)


def test_unknown_numeric_glyph_rejected():
    image=Image.open(ROOT/'public/media/climate/tmax-7days.png').convert('RGB')
    image.paste((255,255,255),(40,1240,100,1300))
    with pytest.raises(ValueError,match='Missing numeric'):C.legend_values(image,REFS)


def test_glyph_templates_recognize_current_labels_without_full_legend_cache():
    image=Image.open(ROOT/'public/media/climate/tmax-7days.png').convert('RGB')
    refs={**REFS,'knownLegends':{}}
    values,_=C.legend_values(image,refs)
    assert values==[60,65,70,75,80,85]


def test_non_png_rejected():
    with pytest.raises(ValueError,match='PNG'):C.describe(b'<html>error</html>','prcp-7days.png',{}, {},{},REFS)


def test_wrong_product_period_rejected(monkeypatch):
    monkeypatch.setattr(C,'transcribe_image',lambda _: 'October 1, 2026 to October 12, 2026')
    raw=(ROOT/'public/media/climate/prcp-7days.png').read_bytes()
    with pytest.raises(ValueError,match='period does not match'):C.describe(raw,'prcp-7days.png',{}, {},{},REFS)


def test_27_published_images_match_text_receipts():
    descriptions=json.loads(C.DESCRIPTIONS.read_text())
    receipts=json.loads(C.RECEIPTS.read_text())
    assert len(descriptions)==receipts['mapCount']==len(receipts['maps'])==27
    for receipt in receipts['maps']:
        name=receipt['name'];raw=(ROOT/'public/media/climate'/name).read_bytes()
        assert C.digest(raw)==receipt['sha256']==descriptions[name]['sha256']
        assert descriptions[name]['periodStart']<=descriptions[name]['periodEnd']
