"""Jabodetabek cities, districts and villages for the profile location dropdowns.

The list lives in accounts/data/jabodetabek.json (Kemendagri codes from wilayah.id, the
same village codes BMKG uses), so the profile page never depends on an outside service.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / 'data' / 'jabodetabek.json'


@lru_cache(maxsize=1)
def regions():
    with open(DATA_FILE, encoding='utf-8') as f:
        return json.load(f)['regions']


@lru_cache(maxsize=1)
def _villages_by_code():
    lookup = {}
    for region in regions():
        for district in region['districts']:
            for code, name in district['villages']:
                lookup[code] = {'code': code, 'village': name, 'district': district['name'], 'city': region['name']}
    return lookup


def find_village(code):
    """{'code', 'village', 'district', 'city'} for a village code, or None."""
    return _villages_by_code().get(code)


def village_choices():
    """Grouped choices for a select: one group per district, labelled 'Tebet, Jakarta Selatan'."""
    groups = [('', 'Choose your area')]
    for region in regions():
        for district in region['districts']:
            groups.append((f'{district["name"]}, {region["name"]}', [tuple(v) for v in district['villages']]))
    return groups
