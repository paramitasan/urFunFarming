"""Turns the shared BMKG forecast into what the Plant care pages show."""
from datetime import timedelta

from django.utils import timezone

from weather.services import mark_good

SLOT_HOURS = 3


def _windows(slots):
    # Joins back-to-back good slots into one window, e.g. 06:00-12:00
    windows = []
    for slot in slots:
        if not slot['good']:
            continue
        start = timezone.localtime(slot['time'])
        end = start + timedelta(hours=SLOT_HOURS)
        last = windows[-1] if windows else None
        if last and last['end'] == start:
            last['end'] = end
            last['slots'].append(slot)
        else:
            windows.append({'start': start, 'end': end, 'slots': [slot]})
    for window in windows:
        first = window['slots'][0]
        window.update(
            kind=first['kind'],
            description=first['description'],
            temp=max(s['temp'] for s in window['slots']),
            rain_mm=sum(s['rain_mm'] for s in window['slots']),
        )
    return windows


def _time_range(window):
    return f'{window["start"]:%H:%M}-{window["end"]:%H:%M}'


def today_card(weather, care_settings):
    """Today's slots marked good or not, plus one line about rain and the best hours."""
    limits = (care_settings.max_rain_mm, care_settings.max_temp_c, care_settings.max_wind_kmh)
    slots = mark_good(weather['today'], *limits) if weather['available'] else []
    if not slots:
        return {'slots': [], 'summary': ''}
    rainy = [s for s in slots if s['kind'] == 'rain' or s['rain_mm'] > float(care_settings.max_rain_mm)]
    parts = []
    if rainy:
        parts.append(f'Rain expected around {timezone.localtime(rainy[0]["time"]):%H:%M}.')
    else:
        parts.append('No rain expected today.')
    windows = _windows(slots)
    if windows:
        parts.append('Outdoor tasks fit best ' + ' or '.join(_time_range(w) for w in windows[:3]) + '.')
    else:
        parts.append('No hours meet your limits today.')
    return {'slots': slots, 'summary': ' '.join(parts)}


def best_times(weather, care_settings, limit=4):
    """Upcoming windows across the next 3 days that meet every threshold, soonest first."""
    if not weather['available']:
        return []
    limits = (care_settings.max_rain_mm, care_settings.max_temp_c, care_settings.max_wind_kmh)
    now = timezone.now()
    upcoming = [s for s in mark_good(weather['slots'], *limits) if s['time'] >= now - timedelta(hours=1)]
    windows = _windows(upcoming)
    for window in windows:
        window['label'] = f'{window["start"]:%a} {_time_range(window)}'
        window['date'] = window['start'].date()
        window['time'] = window['start'].time()
    return windows[:limit]
