"""Helpers for tests in any app: a fake BMKG response and a patch for the request.

    with patch_bmkg(bmkg_payload(slots_from_now())) as remote:
        ...
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.utils import timezone


def slots_from_now(count=8, start_hours=-1, **values):
    """3-hourly local times starting near now, each with the same readings unless given."""
    start = timezone.localtime().replace(minute=0, second=0, microsecond=0) + timedelta(hours=start_hours)
    return [{'time': start + timedelta(hours=3 * i), **values} for i in range(count)]


def bmkg_entry(moment, t=28, tp=0, ws=5, hu=75, desc='Sunny', code=1):
    return {
        'local_datetime': moment.strftime('%Y-%m-%d %H:%M:%S'),
        't': t, 'tp': tp, 'ws': ws, 'hu': hu, 'wd': 'W', 'tcc': 20,
        'weather': code, 'weather_desc': desc, 'weather_desc_en': desc,
        'image': 'https://api-apps.bmkg.go.id/storage/icon/cuaca/cerah-am.svg',
    }


def bmkg_payload(slots, village='Tebet Timur', adm4='31.74.01.1001'):
    """A response shaped like the live API: lokasi plus data[0].cuaca grouped by day."""
    days = {}
    for slot in slots:
        slot = dict(slot)
        moment = slot.pop('time')
        days.setdefault(moment.date(), []).append(bmkg_entry(moment, **slot))
    lokasi = {'adm4': adm4, 'desa': village, 'kecamatan': 'Tebet', 'kotkab': 'Kota Adm. Jakarta Selatan', 'timezone': 'Asia/Jakarta'}
    return {'lokasi': lokasi, 'data': [{'lokasi': lokasi, 'cuaca': list(days.values())}]}


def patch_bmkg(payload=None, side_effect=None):
    """Patches the server-side BMKG request; returns the mock for call checks."""
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return patch('weather.services.requests.get', return_value=response, side_effect=side_effect)
