"""Small, cached Open-Meteo adapter for collection planning, independent of care tasks."""
import json
import math
from datetime import datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.cache import cache
from django.utils import timezone

from marketplace.dates import JAKARTA, jakarta_today
from marketplace.models import HarvestListing


class WeatherUnavailable(Exception):
    pass


def forecast(city):
    latitude, longitude = HarvestListing.CITY_COORDINATES[city]
    key = f'marketplace:weather:{city}:{jakarta_today()}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    params = urlencode({
        'latitude': latitude, 'longitude': longitude,
        'hourly': 'temperature_2m,relative_humidity_2m,precipitation',
        'timezone': 'Asia/Jakarta', 'forecast_days': 7,
    })
    try:
        with urlopen('https://api.open-meteo.com/v1/forecast?' + params, timeout=5) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Response too large')
        payload = json.loads(raw)
        hourly = payload['hourly']
        times = hourly['time']
        temperatures = hourly['temperature_2m']
        humidity = hourly['relative_humidity_2m']
        rain = hourly['precipitation']
        if not isinstance(times, list) or not 1 <= len(times) <= 168:
            raise ValueError('Invalid forecast length')
        if not all(isinstance(values, list) and len(values) == len(times) for values in (temperatures, humidity, rain)):
            raise ValueError('Incomplete hourly forecast')
        slots = []
        for stamp, temp, humid, precipitation in zip(times, temperatures, humidity, rain):
            moment = datetime.fromisoformat(stamp)
            if moment.tzinfo is not None:
                raise ValueError('Expected local time')
            # Missing observations do not become fabricated zero-rain forecasts.
            if any(v is None for v in (temp, humid, precipitation)):
                continue
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (temp, humid, precipitation)):
                raise ValueError('Invalid weather observation')
            if precipitation < 0 or not 0 <= humid <= 100:
                raise ValueError('Invalid precipitation or humidity')
            slots.append({'time': moment, 'temperature': temp, 'humidity': humid, 'rain': precipitation})
        result = {'slots': slots, 'fetched_at': timezone.now().isoformat()}
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as error:
        raise WeatherUnavailable('The forecast is unavailable right now. Please try again shortly.') from error
    cache.set(key, result, 900)
    return result


def filter_pickup_times(data, criteria, listing):
    now = timezone.localtime(timezone.now(), JAKARTA).replace(tzinfo=None)
    matches = []
    for slot in data['slots']:
        moment = slot['time']
        if moment <= now or moment.date() != criteria['date']:
            continue
        if not listing.is_available or moment.date() < listing.available_from:
            continue
        if listing.available_until and moment.date() > listing.available_until:
            continue
        if not criteria['start_time'] <= moment.time() <= criteria['end_time']:
            continue
        if slot['rain'] <= criteria['max_rain'] and slot['temperature'] <= criteria['max_temperature']:
            matches.append(slot)
    return matches
