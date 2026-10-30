"""Turns the shared BMKG forecast into what the Plant care pages show."""
from datetime import datetime, timedelta

from django.utils import timezone

from weather.services import mark_good

SLOT_HOURS = 3
DAYLIGHT_FROM = 5
DAYLIGHT_UNTIL = 17


def _windows(slots):
    # Joins back-to-back good slots into one window, e.g. 06:00-12:00
    windows = []
    for slot in slots:
        if not slot['good']:
            continue
        start = timezone.localtime(slot['time'])
        end = start + timedelta(hours=SLOT_HOURS)
        last = windows[-1] if windows else None
        # Back-to-back on the same day only, so each day gets its own window
        if last and last['end'] == start and last['start'].date() == start.date():
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
    # A window that runs past midnight has no useful end time on the same day
    if window['end'].date() != window['start'].date():
        return f'from {window["start"]:%H:%M}'
    return f'{window["start"]:%H:%M}-{window["end"]:%H:%M}'


def today_card(weather, care_settings):
    """Today's slots marked good or not, plus one line about rain and the best hours."""
    limits = (care_settings.max_rain_mm, care_settings.max_temp_c, care_settings.max_wind_kmh)
    slots = mark_good(weather['today'], *limits) if weather['available'] else []
    if not slots:
        return {'slots': [], 'summary': '', 'rain': False}
    rainy = [s for s in slots if s['kind'] == 'rain' or s['rain_mm'] > float(care_settings.max_rain_mm)]
    parts = []
    if rainy:
        first = rainy[0]
        at = timezone.localtime(first['time'])
        if first['good']:
            # BMKG says rain, but little enough to stay inside the grower's limit
            parts.append(f'Light rain around {at:%H:%M}, within your rain limit.')
        else:
            parts.append(f'Rain expected around {at:%H:%M}.')
    else:
        parts.append('No rain expected today.')
    windows = _windows(slots)
    if all(s['good'] for s in slots):
        parts.append('Every slot today is within your limits.')
    elif windows:
        parts.append('Outdoor tasks fit best ' + ' or '.join(_time_range(w) for w in windows[:3]) + '.')
    else:
        parts.append('No hours meet your limits today.')
    return {'slots': slots, 'summary': ' '.join(parts), 'rain': bool(rainy)}


NO_FORECAST = 'BMKG has no forecast for this time yet. Forecasts cover the next 3 days.'


def _part_of_day(moment):
    if moment.hour < 12:
        return 'morning'
    if moment.hour < 17:
        return 'afternoon'
    if moment.hour < 21:
        return 'evening'
    return 'night'


def _over_limits(slot, care_settings):
    over = []
    if slot['rain_mm'] > float(care_settings.max_rain_mm):
        over.append('rain')
    if slot['temp'] > float(care_settings.max_temp_c):
        over.append('temperature')
    if slot['wind_kmh'] > float(care_settings.max_wind_kmh):
        over.append('wind')
    return over


def slot_message(slot, care_settings):
    """'Tuesday morning looks good: cloudy, 30°, 0 mm rain, wind 5 km/h. Meets all your thresholds.'"""
    moment = timezone.localtime(slot['time'])
    when = f'{moment:%A} {_part_of_day(moment)}'
    reading = (
        f'{slot["description"].lower()}, {slot["temp"]:.0f}°, {slot["rain_mm"]:g} mm rain, '
        f'wind {slot["wind_kmh"]:.0f} km/h'
    )
    over = _over_limits(slot, care_settings)
    if not over:
        return {'good': True, 'kind': slot['kind'], 'text': f'{when} looks good: {reading}. Meets all your thresholds.'}
    limits = ' and '.join(over)
    return {'good': False, 'kind': slot['kind'], 'text': f'{when} may not suit the task: {reading}. Over your {limits} limit.'}


def check_data(weather, care_settings):
    """Every forecast slot with its message, for the form's live weather check."""
    if not weather['available']:
        return []
    return [
        {'start': slot['time'].isoformat(), **slot_message(slot, care_settings)}
        for slot in weather['slots']
    ]


def weather_check(weather, care_settings, target_date, target_time):
    """The message under the date and time fields, or None before a date is picked."""
    if not target_date:
        return None
    if not weather['available']:
        return {'good': None, 'kind': '', 'text': f'{weather["error"]}.'}
    if target_time is None:
        # No time yet: describe the day as a whole
        day = [s for s in mark_good(weather['slots'], care_settings.max_rain_mm, care_settings.max_temp_c,
                                    care_settings.max_wind_kmh)
               if timezone.localtime(s['time']).date() == target_date]
        if not day:
            return {'good': None, 'kind': '', 'text': NO_FORECAST}
        good = [s for s in day if s['good']]
        if not good:
            return {'good': False, 'kind': day[0]['kind'], 'text': f'No slot on {target_date:%A} meets your thresholds.'}
        first = timezone.localtime(good[0]['time'])
        return {'good': True, 'kind': good[0]['kind'], 'text': f'{target_date:%A} has good times from {first:%H:%M}. Pick a time to check it.'}
    moment = datetime.combine(target_date, target_time, tzinfo=timezone.get_current_timezone())
    for slot in weather['slots']:
        if slot['time'] <= moment < slot['time'] + timedelta(hours=SLOT_HOURS):
            return slot_message(slot, care_settings)
    return {'good': None, 'kind': '', 'text': NO_FORECAST}


def best_times(weather, care_settings, limit=4):
    """Upcoming daytime windows in the next 3 days that meet every threshold, soonest first."""
    if not weather['available']:
        return []
    limits = (care_settings.max_rain_mm, care_settings.max_temp_c, care_settings.max_wind_kmh)
    now = timezone.now()
    # Outdoor care happens in daylight: slots starting from 05:00 up to 17:00
    upcoming = [
        s for s in mark_good(weather['slots'], *limits)
        if s['time'] >= now and DAYLIGHT_FROM <= timezone.localtime(s['time']).hour <= DAYLIGHT_UNTIL
    ]
    windows = _windows(upcoming)
    for window in windows:
        window['label'] = f'{window["start"]:%a} {_time_range(window)}'
        window['date'] = window['start'].date()
        window['time'] = window['start'].time()
    return windows[:limit]
