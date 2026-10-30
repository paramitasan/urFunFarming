import io
from datetime import datetime, time, timedelta

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from marketplace.dates import JAKARTA, jakarta_today
from marketplace.models import HarvestListing
from marketplace.tests.helpers import MarketplaceCase
from marketplace.weather import CITY_ADM4, WeatherUnavailable, filter_pickup_times, forecast
from weather.services import BMKG_URL
from weather.testing import bmkg_payload, patch_bmkg


def tomorrow_at(hour):
    return datetime.combine(jakarta_today()+timedelta(days=1), time(hour), tzinfo=JAKARTA)


def weather_payload(**changes):
    readings = [(8, 27, 0, 70), (11, 33, 2, 75), (14, 36, 0, 65), (17, 30, .5, 70)]
    slots = [{'time': tomorrow_at(h), 't': t, 'tp': tp, 'hu': hu, 'ws': 6} for h, t, tp, hu in readings]
    for index, values in changes.items():
        slots[int(index[1:])].update(values)
    return bmkg_payload(slots, village='Beji', adm4='32.76.06.1001')


class PickupForecastTests(MarketplaceCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('marketplace:weather', args=[self.listing.pk])
        self.criteria = {'date': (jakarta_today()+timedelta(days=1)).isoformat(), 'start_time': '08:00', 'end_time': '18:00', 'max_rain': '1', 'max_temperature': '35'}
        self.patcher = patch_bmkg(weather_payload())
        self.remote = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def use_payload(self, payload):
        cache.clear()
        self.remote.return_value.json.return_value = payload

    def test_bmkg_slots_are_filtered_and_cached_by_collection_city(self):
        response = self.client.get(self.url, self.criteria, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['timezone'], 'Asia/Jakarta')
        self.assertEqual(data['source'], 'BMKG')
        self.assertEqual([x['time'][11:19] for x in data['results']], ['08:00:00', '17:00:00'])
        self.assertEqual((data['results'][0]['temp'], data['results'][0]['humidity']), (27, 70))
        # Depok maps to a fixed village code near the city centre
        self.remote.assert_called_once_with(BMKG_URL, params={'adm4': CITY_ADM4['Depok']}, timeout=5)
        self.client.get(self.url, {**self.criteria, 'max_rain': '3'}, HTTP_ACCEPT='application/json')
        self.assertEqual(self.remote.call_count, 1)

    def test_html_forecast_and_ajax_fragment_credit_bmkg(self):
        response = self.client.get(self.url, self.criteria)
        self.assertContains(response, '08:00 WIB')
        self.assertContains(response, 'Fresh basil')
        self.assertContains(response, 'Source: <a href="https://www.bmkg.go.id/"')
        self.assertNotContains(response, 'Open-Meteo')
        response = self.client.get(self.url, self.criteria, HTTP_X_REQUESTED_WITH='fetch')
        self.assertContains(response, '17:00 WIB')
        self.assertContains(response, 'Source: <a')
        self.assertNotContains(response, '<html')

    def test_invalid_filters_do_not_call_the_external_api(self):
        beyond_bmkg = (jakarta_today()+timedelta(days=3)).isoformat()
        for changes in ({'max_rain': '-1'}, {'date': beyond_bmkg}):
            for headers in [{}, {'HTTP_X_REQUESTED_WITH': 'fetch'}, {'HTTP_ACCEPT': 'application/json'}]:
                response = self.client.get(self.url, {**self.criteria, **changes}, **headers)
                self.assertEqual(response.status_code, 400)
        self.remote.assert_not_called()

    def test_network_failure_shows_the_fallback_and_is_never_faked(self):
        self.remote.side_effect = requests.ConnectionError('network down')
        for headers in [{}, {'HTTP_X_REQUESTED_WITH': 'fetch'}, {'HTTP_ACCEPT': 'application/json'}]:
            response = self.client.get(self.url, self.criteria, **headers)
            self.assertEqual(response.status_code, 503)
            self.assertContains(response, 'Weather is unavailable right now', status_code=503)
        response = self.client.get(self.url, self.criteria)
        self.assertContains(response, 'Source: <a', status_code=503)

    def test_timeout_and_malformed_api_responses_fail_safely(self):
        for broken in [{}, {'data': []}, weather_payload(s0={'tp': -1}), weather_payload(s0={'t': 'bad'})]:
            with self.subTest(broken=str(broken)[:40]):
                self.use_payload(broken)
                self.assertEqual(self.client.get(self.url, self.criteria, HTTP_ACCEPT='application/json').status_code, 503)
        cache.clear()
        self.remote.side_effect = requests.Timeout()
        with self.assertRaises(WeatherUnavailable):
            forecast('Depok')

    def test_missing_readings_are_skipped(self):
        self.use_payload(weather_payload(s0={'tp': None}))
        self.assertEqual(len(forecast('Depok')['slots']), 3)

    def test_pickup_filters_respect_offer_dates_times_and_current_time(self):
        date = jakarta_today()+timedelta(days=1)
        criteria = {'date': date, 'start_time': time(9), 'end_time': time(12), 'max_rain': 3, 'max_temperature': 35}
        data = forecast('Depok')
        self.assertEqual([timezone.localtime(s['time']).hour for s in filter_pickup_times(data, criteria, self.listing)], [11])
        self.listing.available_until = jakarta_today()
        self.assertEqual(filter_pickup_times(data, criteria, self.listing), [])
        self.listing.available_until = None
        self.listing.available_from = date+timedelta(days=1)
        self.assertEqual(filter_pickup_times(data, criteria, self.listing), [])
        self.listing.available_from = jakarta_today()
        self.listing.is_available = False
        self.assertEqual(filter_pickup_times(data, criteria, self.listing), [])

    def test_no_matching_hours_is_a_normal_empty_result(self):
        response = self.client.get(self.url, {**self.criteria, 'start_time': '20:00', 'end_time': '21:00'}, HTTP_X_REQUESTED_WITH='fetch')
        self.assertContains(response, 'No upcoming collection times match')

    def test_hidden_offer_and_invalid_methods_are_not_exposed(self):
        self.listing.is_available = False
        self.listing.save()
        self.assertEqual(self.client.get(self.url, self.criteria).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.criteria).status_code, 405)


class DemoSeedTests(MarketplaceCase):
    def test_fifty_demo_records_are_idempotent_and_real_records_survive(self):
        output = io.StringIO()
        call_command('seed_marketplace', stdout=output)
        self.assertEqual(HarvestListing.objects.filter(is_demo=True).count(), 50)
        self.assertEqual(HarvestListing.objects.available_now().filter(is_demo=True).count(), 50)
        self.assertEqual(User.objects.filter(username__startswith='demo_grower_').count(), 10)
        self.assertFalse(any(u.has_usable_password() for u in User.objects.filter(username__startswith='demo_grower_')))
        ids = set(HarvestListing.objects.filter(is_demo=True).values_list('pk', flat=True))
        call_command('seed_marketplace', stdout=io.StringIO())
        self.assertEqual(set(HarvestListing.objects.filter(is_demo=True).values_list('pk', flat=True)), ids)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, 'Fresh basil')
        self.assertFalse(self.listing.is_demo)
        self.assertIn('50 demo harvest', output.getvalue())

    def test_collision_with_a_real_account_aborts_without_changing_it(self):
        real_user = User.objects.create_user('demo_grower_01', password='keep-this-password')
        with self.assertRaises(CommandError):
            call_command('seed_marketplace', stdout=io.StringIO())
        real_user.refresh_from_db()
        self.assertTrue(real_user.check_password('keep-this-password'))
        self.assertEqual(HarvestListing.objects.filter(is_demo=True).count(), 0)
