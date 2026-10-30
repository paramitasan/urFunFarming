"""Pickup-time planner for collection, built on the shared BMKG weather service."""
from django.utils import timezone

from marketplace.dates import JAKARTA
from weather.services import WeatherUnavailable, get_forecast  # noqa: F401 (views import WeatherUnavailable from here)

# A BMKG village code near each collection city's centre, never a grower's address
CITY_ADM4 = {
    'Depok': '32.76.06.1001',      # Beji
    'Jakarta': '31.71.01.1001',    # Gambir
    'Bogor': '32.71.01.1001',      # Batu Tulis
    'Bekasi': '32.75.01.1001',     # Bekasijaya
    'Tangerang': '36.71.01.1001',  # Sukarasa
}


def forecast(city):
    return get_forecast(CITY_ADM4[city])


def filter_pickup_times(data, criteria, listing):
    now = timezone.now()
    matches = []
    for slot in data['slots']:
        moment = timezone.localtime(slot['time'], JAKARTA)
        if slot['time'] <= now or moment.date() != criteria['date']:
            continue
        if not listing.is_available or moment.date() < listing.available_from:
            continue
        if listing.available_until and moment.date() > listing.available_until:
            continue
        if not criteria['start_time'] <= moment.time().replace(tzinfo=None) <= criteria['end_time']:
            continue
        if slot['rain_mm'] <= criteria['max_rain'] and slot['temp'] <= criteria['max_temperature']:
            matches.append(slot)
    return matches
