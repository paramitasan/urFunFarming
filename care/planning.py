"""Turns a raw forecast into advice about when a care task should happen.

The forecast itself comes from marketplace.weather, which the group already uses
for collection planning. Reusing it keeps one Open-Meteo adapter in the project
instead of two.
"""
from datetime import datetime, timedelta

from django.utils import timezone

from marketplace.dates import JAKARTA
from marketplace.weather import WeatherUnavailable, forecast

# How many suggestions the form offers at most.
SUGGESTION_LIMIT = 6


def _now_naive():
    # weather.forecast returns naive times in Jakarta local time, so comparisons
    # have to happen in the same shape.
    return timezone.localtime(timezone.now(), JAKARTA).replace(tzinfo=None)


def load_forecast(preference):
    """The forecast for the grower's city, or None when the service is down."""
    try:
        return forecast(preference.city)
    except WeatherUnavailable:
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
        if not day:
            return {'state': 'unknown', 'text': 'The forecast does not reach that day yet. It covers about seven days.'}
        good = [slot for slot in day if preference.accepts(slot)]
        if not good:
            return {'state': 'poor', 'text': 'No hour that day stays inside your limits.'}
        hours = ', '.join(slot['time'].strftime('%H:%M') for slot in good[:4])
        return {'state': 'good', 'text': f'{len(good)} of {len(day)} hours work that day, for example {hours}.'}

    moment = datetime.combine(planned_for, planned_time)
    slot = slot_at(data, moment)
    if slot is None:
        return {'state': 'unknown', 'text': 'The forecast does not reach that time yet. It covers about seven days.'}
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
    return {'state': 'good', 'text': f'{len(good)} hours left today work, starting at {first}.'}
