"""Shared BMKG weather service.

Every page that shows weather goes through this file, so the server makes at most
one BMKG request per location per hour and the browser never calls BMKG itself.
API docs: https://data.bmkg.go.id/prakiraan-cuaca/
"""
import math
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

BMKG_URL = 'https://api.bmkg.go.id/publik/prakiraan-cuaca'
SOURCE = 'BMKG'
UNAVAILABLE_MESSAGE = 'Weather is unavailable right now'
TIMEOUT_SECONDS = 5
# BMKG updates twice a day and allows 60 requests per minute per IP
CACHE_SECONDS = 60 * 60
# After a failure, wait a few minutes before asking BMKG again
FAILURE_CACHE_SECONDS = 5 * 60
JAKARTA = ZoneInfo('Asia/Jakarta')
# Village code (kode wilayah tingkat IV), e.g. 31.71.03.1001
ADM4_PATTERN = re.compile(r'^\d{2}\.\d{2}\.\d{2}\.\d{4}$')


class WeatherUnavailable(Exception):
    pass


def default_adm4():
    return getattr(settings, 'BMKG_DEFAULT_ADM4', '') or '31.71.03.1001'


def _number(value, low=None, high=None):
    # Booleans, text, NaN and out-of-range values mean the response is broken
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid weather value')
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError('Weather value out of range')
    return value


def _kind(code, description, moment):
    # Picks one of our own icons: rain, cloud, sun or moon
    text = description.lower()
    if (isinstance(code, int) and code >= 60) or 'rain' in text or 'thunder' in text:
        return 'rain'
    if (isinstance(code, int) and code >= 3) or 'cloud' in text or 'fog' in text or 'haze' in text:
        return 'cloud'
    return 'sun' if 6 <= moment.hour < 18 else 'moon'


def normalize(payload):
    """Turn a BMKG response into {'location', 'slots', 'fetched_at', 'source'}.

    Each slot is a simple dict: time, temp, rain_mm, wind_kmh, humidity,
    description, icon and kind. Raises ValueError, KeyError, TypeError or
    IndexError when the response is not the shape we expect.
    """
    if not isinstance(payload, dict):
        raise ValueError('Expected a JSON object')
    # The live API nests the days under data[0]; the README examples put them at the top
    block = payload['data'][0] if 'data' in payload else payload
    days = block['cuaca']
    location = payload.get('lokasi') or block.get('lokasi') or {}
    if not isinstance(days, list) or not days:
        raise ValueError('No forecast days')
    try:
        zone = ZoneInfo(location.get('timezone') or 'Asia/Jakarta')
    except (ZoneInfoNotFoundError, ValueError):
        zone = JAKARTA

    slots = []
    for day in days:
        if not isinstance(day, list):
            raise ValueError('Expected a list of 3-hourly entries')
        for entry in day:
            moment = datetime.strptime(entry['local_datetime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=zone)
            values = (entry.get('t'), entry.get('tp'), entry.get('ws'), entry.get('hu'))
            # A missing reading is skipped, never turned into a made-up zero
            if any(value is None for value in values):
                continue
            temp, rain, wind, humidity = values
            description = entry.get('weather_desc_en') or entry.get('weather_desc') or ''
            slots.append({
                'time': moment,
                'temp': _number(temp, -20, 60),
                'rain_mm': _number(rain, 0),
                'wind_kmh': _number(wind, 0),
                'humidity': _number(humidity, 0, 100),
                'description': description,
                'icon': entry.get('image') or '',
                'kind': _kind(entry.get('weather'), description, moment),
            })
    if not slots:
        raise ValueError('No usable forecast entries')
    slots.sort(key=lambda slot: slot['time'])
    return {
        'location': {
            'adm4': location.get('adm4', ''),
            'village': location.get('desa', ''),
            'district': location.get('kecamatan', ''),
            'city': location.get('kotkab', ''),
        },
        'slots': slots,
        'fetched_at': timezone.now(),
        'source': SOURCE,
    }


def get_forecast(adm4):
    """Normalized 3-day forecast for one village code, cached for an hour.

    Raises WeatherUnavailable when BMKG fails, times out or sends bad data.
    """
    adm4 = (adm4 or '').strip()
    if not ADM4_PATTERN.match(adm4):
        raise WeatherUnavailable(UNAVAILABLE_MESSAGE)
    key = f'weather:bmkg:{adm4}'
    cached = cache.get(key)
    if cached is not None:
        if cached.get('unavailable'):
            raise WeatherUnavailable(UNAVAILABLE_MESSAGE)
        return cached
    try:
        response = requests.get(BMKG_URL, params={'adm4': adm4}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        data = normalize(response.json())
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        cache.set(key, {'unavailable': True}, FAILURE_CACHE_SECONDS)
        raise WeatherUnavailable(UNAVAILABLE_MESSAGE) from error
    cache.set(key, data, CACHE_SECONDS)
    return data


def location_for_user(user):
    """The village code and area name to use for this user.

    Uses profile.adm4_code (from the profile location feature) and falls back to
    the BMKG_DEFAULT_ADM4 setting when it is empty, invalid or not there yet.
    """
    profile = getattr(user, 'profile', None) if getattr(user, 'is_authenticated', False) else None
    code = (getattr(profile, 'adm4_code', '') or '').strip()
    if ADM4_PATTERN.match(code):
        return {'adm4': code, 'name': getattr(profile, 'area', '') or '', 'has_location': True}
    return {'adm4': default_adm4(), 'name': '', 'has_location': False}


def meets_thresholds(slot, max_rain_mm, max_temp_c, max_wind_kmh):
    # A "good" slot is within all three of the user's limits
    return (
        slot['rain_mm'] <= float(max_rain_mm)
        and slot['temp'] <= float(max_temp_c)
        and slot['wind_kmh'] <= float(max_wind_kmh)
    )


def mark_good(slots, max_rain_mm, max_temp_c, max_wind_kmh):
    # Copies, so the cached slots are never changed
    return [{**slot, 'good': meets_thresholds(slot, max_rain_mm, max_temp_c, max_wind_kmh)} for slot in slots]


def forecast_for_user(user):
    """Everything a template needs to show weather for this user. Never raises.

    Keys: available, source, error, location_name, has_location, slots (next
    3 days), today (today's slots, or the next ones late at night), later (the
    slots after today's), current (the slot for right now) and fetched_at.
    """
    place = location_for_user(user)
    result = {
        'available': False,
        'source': SOURCE,
        'error': '',
        'location_name': place['name'],
        'has_location': place['has_location'],
        'slots': [],
        'today': [],
        'later': [],
        'current': None,
        'fetched_at': None,
    }
    try:
        data = get_forecast(place['adm4'])
    except WeatherUnavailable as error:
        result['error'] = str(error)
        return result

    now = timezone.now()
    today = timezone.localdate()
    # Keep the slot that is still running (each one covers 3 hours)
    upcoming = [slot for slot in data['slots'] if slot['time'] > now - timedelta(hours=3)]
    current = [slot for slot in upcoming if slot['time'] <= now]
    shown_today = [slot for slot in upcoming if timezone.localtime(slot['time']).date() == today] or upcoming[:8]
    result.update(
        available=bool(upcoming),
        error='' if upcoming else UNAVAILABLE_MESSAGE,
        location_name=place['name'] or data['location']['village'] or data['location']['district'],
        slots=upcoming,
        today=shown_today,
        later=[slot for slot in upcoming if slot['time'] > shown_today[-1]['time']] if shown_today else [],
        current=current[-1] if current else (upcoming[0] if upcoming else None),
        fetched_at=data['fetched_at'],
    )
    return result
