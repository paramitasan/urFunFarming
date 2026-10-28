import io
import json
from datetime import datetime, time, timedelta
from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from marketplace.dates import jakarta_today
from marketplace.models import HarvestListing
from marketplace.tests.helpers import MarketplaceCase
from marketplace.weather import WeatherUnavailable, filter_pickup_times, forecast


def weather_payload():
    tomorrow = jakarta_today()+timedelta(days=1)
    return {'hourly': {'time': [f'{tomorrow}T{h:02}:00' for h in (8, 9, 10, 11)],
                       'temperature_2m': [27, 33, 36, 30], 'precipitation': [0, 2, 0, .5],
                       'relative_humidity_2m': [70, 75, 65, 70]}}


class PickupForecastTests(MarketplaceCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('marketplace:weather', args=[self.listing.pk])
        self.criteria = {'date': (jakarta_today()+timedelta(days=1)).isoformat(), 'start_time': '08:00', 'end_time': '18:00', 'max_rain': '1', 'max_temperature': '35'}
        self.patcher = patch('marketplace.weather.urlopen')
        self.remote = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.remote.return_value.__enter__.return_value.read.return_value = json.dumps(weather_payload()).encode()

    def test_external_hourly_data_is_filtered_and_cached_by_collection_city(self):
        response = self.client.get(self.url, self.criteria, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['timezone'], 'Asia/Jakarta')
        self.assertEqual(data['source'], 'Open-Meteo')
        self.assertEqual([x['time'][-8:] for x in data['results']], ['08:00:00', '11:00:00'])
        self.assertEqual(data['results'][0]['humidity'], 70)
        call = self.remote.call_args
        self.assertIn('api.open-meteo.com/v1/forecast', call.args[0])
        self.assertIn('timezone=Asia%2FJakarta', call.args[0])
        self.assertEqual(call.kwargs['timeout'], 5)
        self.client.get(self.url, {**self.criteria, 'max_rain': '3'}, HTTP_ACCEPT='application/json')
        self.assertEqual(self.remote.call_count, 1)

    def test_html_forecast_and_ajax_fragment(self):
        response = self.client.get(self.url, self.criteria)
        self.assertContains(response, '08:00 WIB')
        self.assertContains(response, 'Fresh basil')
        response = self.client.get(self.url, self.criteria, HTTP_X_REQUESTED_WITH='fetch')
        self.assertContains(response, '11:00 WIB')
        self.assertNotContains(response, '<html')

    def test_invalid_filters_do_not_call_the_external_api(self):
        for headers in [{}, {'HTTP_X_REQUESTED_WITH': 'fetch'}, {'HTTP_ACCEPT': 'application/json'}]:
            response = self.client.get(self.url, {**self.criteria, 'max_rain': '-1'}, **headers)
            self.assertEqual(response.status_code, 400)
        self.remote.assert_not_called()

    def test_network_failure_is_explicit_and_never_faked(self):
        self.remote.side_effect = URLError('network down')
        for headers in [{}, {'HTTP_X_REQUESTED_WITH': 'fetch'}, {'HTTP_ACCEPT': 'application/json'}]:
            response = self.client.get(self.url, self.criteria, **headers)
            self.assertEqual(response.status_code, 503)
            self.assertContains(response, 'unavailable', status_code=503)

    def test_timeout_and_malformed_api_responses_fail_safely(self):
        for broken in [b'not json', b'{}', b'{"hourly":null}', json.dumps({'hourly': {'time': []}}).encode(),
                       json.dumps({'hourly': {**weather_payload()['hourly'], 'precipitation': [0]}}).encode(),
                       json.dumps({'hourly': {**weather_payload()['hourly'], 'precipitation': [-1, 0, 0, 0]}}).encode(),
                       json.dumps({'hourly': {**weather_payload()['hourly'], 'temperature_2m': ['bad', 0, 0, 0]}}).encode()]:
            with self.subTest(broken=broken[:40]):
                cache.clear()
                self.remote.return_value.__enter__.return_value.read.return_value = broken
                self.assertEqual(self.client.get(self.url, self.criteria, HTTP_ACCEPT='application/json').status_code, 503)
        self.remote.side_effect = TimeoutError()
        with self.assertRaises(WeatherUnavailable):
            forecast('Depok')

    def test_large_response_is_rejected_and_null_observations_are_skipped(self):
        self.remote.return_value.__enter__.return_value.read.return_value = b'x'*(1024*1024+1)
        with self.assertRaises(WeatherUnavailable):
            forecast('Depok')
        payload = weather_payload()
        payload['hourly']['precipitation'][0] = None
        self.remote.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        self.assertEqual(len(forecast('Depok')['slots']), 3)

    def test_pickup_filters_respect_offer_dates_times_and_current_time(self):
        date = jakarta_today()+timedelta(days=1)
        criteria = {'date': date, 'start_time': time(9), 'end_time': time(10), 'max_rain': 3, 'max_temperature': 35}
        data = forecast('Depok')
        self.assertEqual([s['time'].hour for s in filter_pickup_times(data, criteria, self.listing)], [9])
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
