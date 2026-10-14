"""Reviewed document alternatives must remain tied to their exact source files."""
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
import pytest

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = json.loads((ROOT / 'data/expanded/products.json').read_text())['pages']
DOCUMENTS = [page for page in PRODUCTS.values() if page.get('download')]


@pytest.mark.parametrize('page', DOCUMENTS, ids=lambda page: page['download'].split('/')[-1])
def test_document_content_and_source_match(page):
    document_id = Path(page['download']).stem
    alternative = json.loads((ROOT / 'data/document-alternatives' / f'{document_id}.json').read_text())
    source_bytes = (ROOT / 'public' / page['download'].lstrip('/')).read_bytes()
    assert alternative['sourceSha256'] == page['source']['sha256'] == hashlib.sha256(source_bytes).hexdigest()
    assert alternative['status'] in ('full', 'partial')
    assert alternative['title'].strip()
    soup = BeautifulSoup(alternative['html'], 'html.parser')
    assert soup.get_text(' ', strip=True)
    assert not soup.select('script, iframe, object, embed, h1')
    for tag in soup.find_all(True):
        assert not any(attr.lower().startswith('on') for attr in tag.attrs)
    for table in soup.find_all('table'):
        assert table.find('caption')
        assert table.select('thead th[scope="col"]')
        for row in table.select('tbody tr'):
            assert row.find(['th', 'td'], recursive=False).get('scope') == 'row'
        region = table.find_parent(class_='table-wrap')
        assert region
        if len(table.select('thead th')) > 3:
            assert region.get('tabindex') == '0' and region.get('role') == 'region'
            assert region.get('aria-label') or region.get('aria-labelledby')
    for link in soup.find_all('a', href=True):
        assert link.get_text(' ', strip=True)
        assert link['href'].startswith(('/', '#', 'https://', 'mailto:'))
