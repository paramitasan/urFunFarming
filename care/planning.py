"""Turns a raw forecast into advice about when a care task should happen.

The forecast itself comes from marketplace.weather, which the group already uses
for collection planning. Reusing it keeps one Open-Meteo adapter in the project
instead of two.
"""
from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.utils import timezone

from marketplace.dates import JAKARTA
from marketplace.weather import WeatherUnavailable, forecast

# How many suggestions the form offers at most.
SUGGESTION_LIMIT = 6
# While the service is down, remember that for a short while. Without this every
# page view waits for the same five second timeout again.
OUTAGE_MEMORY_SECONDS = 120


def _now_naive():
    # weather.forecast returns naive times in Jakarta local time, so comparisons
    # have to happen in the same shape.
    return timezone.localtime(timezone.now(), JAKARTA).replace(tzinfo=None)


def load_forecast(preference):
    """The forecast for the grower's city, or None when the service is down."""
    outage_key = f'care:forecast-outage:{preference.city}'
    if cache.get(outage_key):
        return None
    try:
        return forecast(preference.city)
    except WeatherUnavailable:
        cache.set(outage_key, True, OUTAGE_MEMORY_SECONDS)
        return None


def upcoming_slots(data):
    if not data:
        return []
    now = _now_naive()
    return [slot for slot in data['slots'] if slot['time'] > now]


def suggestions(data, preference, limit=SUGGESTION_LIMIT):
    """The next few hours that stay inside every limit the grower set."""
    return [slot for slot in upcoming_slots(data) if preference.accepts(slot)][:limit]


def slot_at(data, moment):
    """The forecast hour covering a moment, or None if the forecast does not reach it."""
    if not data:
        return None
    for slot in data['slots']:
        if slot['time'] <= moment < slot['time'] + timedelta(hours=1):
            return slot
    return None


def slots_on(data, day):
    if not data:
        return []
    return [slot for slot in data['slots'] if slot['time'].date() == day]


def _plural(count, word):
    return f'{count} {word}' if count == 1 else f'{count} {word}s'


def _describe(slot):
    return (
        f"{slot['temperature']:.0f} degrees, "
        f"{slot['humidity']:.0f} percent humidity, "
        f"{slot['rain']:.1f} mm rain"
    )


def _reasons(slot, preference):
    """Which limits a slot breaks, in words the grower can act on."""
    broken = []
    if slot['rain'] > float(preference.max_rain_mm):
        broken.append(f"rain {slot['rain']:.1f} mm is above your {preference.max_rain_mm} mm")
    if slot['temperature'] > float(preference.max_temperature_c):
        broken.append(f"{slot['temperature']:.0f} degrees is above your {preference.max_temperature_c}")
    if slot['humidity'] > preference.max_humidity_percent:
        broken.append(f"humidity {slot['humidity']:.0f} percent is above your {preference.max_humidity_percent}")
    return broken


def _out_of_range_text(data, moment):
    """Says which side of the forecast the moment falls on, rather than always 'not yet'."""
    if not data or not data['slots']:
        return 'The forecast is unavailable right now.'
    if moment < data['slots'][0]['time']:
        return 'That time has already passed, so there is no forecast for it.'
    return 'The forecast does not reach that far yet. It covers about seven days.'


def verdict(data, preference, planned_for, planned_time=None):
    """Judge the chosen moment.

    Returns a dict with a state the template can style on, plus a sentence.
    State is 'good', 'poor', 'unknown' or 'none'.
    """
    if planned_for is None:
        return {'state': 'none', 'text': 'Pick a date to see the forecast.'}
    if data is None:
        return {'state': 'unknown', 'text': 'The forecast is unavailable right now.'}

    if planned_time is None:
        day = slots_on(data, planned_for)
        # For today, hours that are already over are no use as a suggestion.
        if planned_for == timezone.localdate(timezone=JAKARTA):
            now = _now_naive()
            day = [slot for slot in day if slot['time'] > now]
        if not day:
            return {'state': 'unknown', 'text': _out_of_range_text(data, datetime.combine(planned_for, time(12, 0)))}
        good = [slot for slot in day if preference.accepts(slot)]
        if not good:
            return {'state': 'poor', 'text': 'No hour left that day stays inside your limits.'}
        hours = ', '.join(slot['time'].strftime('%H:%M') for slot in good[:4])
        return {'state': 'good', 'text': f'{len(good)} of {_plural(len(day), "hour")} work that day, for example {hours}.'}

    moment = datetime.combine(planned_for, planned_time)
    slot = slot_at(data, moment)
    if slot is None:
        return {'state': 'unknown', 'text': _out_of_range_text(data, moment)}
    if preference.accepts(slot):
        return {'state': 'good', 'text': f'Good conditions: {_describe(slot)}.'}
    return {'state': 'poor', 'text': 'Outside your limits: ' + ', '.join(_reasons(slot, preference)) + '.'}


def today_outlook(data, preference):
    """A one-line summary for the list page."""
    if data is None:
        return {'state': 'unknown', 'text': 'The forecast is unavailable right now.'}
    rest_of_today = [slot for slot in upcoming_slots(data) if slot['time'].date() == timezone.localdate(timezone=JAKARTA)]
    if not rest_of_today:
        return {'state': 'none', 'text': 'No forecast hours left for today.'}
    good = [slot for slot in rest_of_today if preference.accepts(slot)]
    if not good:
        return {'state': 'poor', 'text': 'No hour left today stays inside your limits.'}
    first = good[0]['time'].strftime('%H:%M')
    return {'state': 'good', 'text': f'{_plural(len(good), "hour")} left today work, starting at {first}.'}
