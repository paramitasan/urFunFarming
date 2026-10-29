from datetime import datetime
from unittest.mock import patch

import requests
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings

from accounts.models import Profile
from weather.services import (
    BMKG_URL,
    TIMEOUT_SECONDS,
    JAKARTA,
    UNAVAILABLE_MESSAGE,
    WeatherUnavailable,
    forecast_for_user,
    get_forecast,
    location_for_user,
    mark_good,
    meets_thresholds,
    normalize,
)
from weather.testing import bmkg_entry, bmkg_payload, patch_bmkg, slots_from_now

TEBET = '31.74.01.1001'


class NormalizeTests(TestCase):
    def test_live_response_shape_becomes_simple_slots(self):
        morning = datetime(2026, 10, 28, 8, 0, tzinfo=JAKARTA)
        payload = bmkg_payload([
            {'time': morning.replace(hour=14), 't': 29, 'tp': 3.4, 'ws': 12.5, 'hu': 88, 'desc': 'Light Rain', 'code': 61},
            {'time': morning, 't': 27, 'tp': 0, 'ws': 4, 'hu': 80, 'desc': 'Mostly Cloudy', 'code': 3},
        ])
        data = normalize(payload)
        self.assertEqual(data['source'], 'BMKG')
        self.assertEqual(data['location']['village'], 'Tebet Barat')
        first, second = data['slots']
        # Sorted by time, with the agreed keys
        self.assertEqual(first['time'], morning)
        self.assertEqual(
            {k: first[k] for k in ('temp', 'rain_mm', 'wind_kmh', 'humidity', 'description', 'kind')},
            {'temp': 27, 'rain_mm': 0, 'wind_kmh': 4, 'humidity': 80, 'description': 'Mostly Cloudy', 'kind': 'cloud'},
        )
        self.assertTrue(first['icon'].startswith('https://api-apps.bmkg.go.id/'))
        self.assertEqual((second['rain_mm'], second['kind']), (3.4, 'rain'))

    def test_readme_shape_and_missing_readings(self):
        moment = datetime(2026, 10, 28, 21, 0, tzinfo=JAKARTA)
        missing = bmkg_entry(moment.replace(hour=18))
        missing['tp'] = None
        payload = {'lokasi': {'desa': 'Gambir'}, 'cuaca': [[missing, bmkg_entry(moment, desc='Clear', code=0)]]}
        slots = normalize(payload)['slots']
        # The slot with no rain reading is skipped, not filled with zero
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]['kind'], 'moon')

    def test_indonesian_description_is_used_when_english_is_missing(self):
        entry = bmkg_entry(datetime(2026, 10, 28, 9, 0, tzinfo=JAKARTA))
        entry['weather_desc_en'] = ''
        entry['weather_desc'] = 'Cerah'
        self.assertEqual(normalize({'cuaca': [[entry]]})['slots'][0]['description'], 'Cerah')


class GetForecastTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_calls_bmkg_from_the_server_with_a_short_timeout(self):
        with patch_bmkg(bmkg_payload(slots_from_now())) as remote:
            data = get_forecast(TEBET)
        self.assertEqual(len(data['slots']), 8)
        remote.assert_called_once_with(BMKG_URL, params={'adm4': TEBET}, timeout=TIMEOUT_SECONDS)
        self.assertLessEqual(TIMEOUT_SECONDS, 5)

    def test_each_location_is_cached_for_an_hour(self):
        with patch_bmkg(bmkg_payload(slots_from_now())) as remote, patch('weather.services.cache.set', wraps=cache.set) as setter:
            get_forecast(TEBET)
            get_forecast(TEBET)
            self.assertEqual(remote.call_count, 1)
            self.assertEqual(setter.call_args.args[2], 60 * 60)
            get_forecast('32.76.06.1001')
            self.assertEqual(remote.call_count, 2)

    def test_failures_raise_weather_unavailable(self):
        broken_payloads = [
            'not a dict', {}, {'data': []}, {'cuaca': []}, {'cuaca': ['not a day']},
            {'cuaca': [[{'t': 28}]]},  # no local_datetime
            bmkg_payload(slots_from_now(t='hot')),
            bmkg_payload(slots_from_now(tp=-1)),
            bmkg_payload(slots_from_now(hu=150)),
            bmkg_payload(slots_from_now(ws=float('nan'))),
        ]
        for payload in broken_payloads:
            with self.subTest(payload=str(payload)[:50]):
                cache.clear()
                with patch_bmkg(payload), self.assertRaises(WeatherUnavailable):
                    get_forecast(TEBET)
        for error in (requests.Timeout(), requests.ConnectionError(), requests.HTTPError('500'), ValueError('bad json')):
            with self.subTest(error=error):
                cache.clear()
                with patch_bmkg(side_effect=error), self.assertRaises(WeatherUnavailable):
                    get_forecast(TEBET)

    def test_a_failure_is_remembered_briefly_so_bmkg_is_not_hammered(self):
        with patch_bmkg(side_effect=requests.Timeout()) as remote:
            for _ in range(3):
                with self.assertRaises(WeatherUnavailable):
                    get_forecast(TEBET)
        self.assertEqual(remote.call_count, 1)

    def test_invalid_codes_never_reach_bmkg(self):
        with patch_bmkg(bmkg_payload(slots_from_now())) as remote:
            for code in ('', 'Tebet', '31.74.01', '31.74.01.1001&x=1'):
                with self.assertRaises(WeatherUnavailable):
                    get_forecast(code)
        remote.assert_not_called()


class ThresholdTests(TestCase):
    slot = {'rain_mm': 2, 'temp': 32, 'wind_kmh': 15}

    def test_slot_on_every_limit_is_still_good(self):
        self.assertTrue(meets_thresholds(self.slot, 2, 32, 15))

    def test_any_limit_exceeded_is_not_good(self):
        self.assertFalse(meets_thresholds({**self.slot, 'rain_mm': 2.1}, 2, 32, 15))
        self.assertFalse(meets_thresholds({**self.slot, 'temp': 33}, 2, 32, 15))
        self.assertFalse(meets_thresholds({**self.slot, 'wind_kmh': 16}, 2, 32, 15))

    def test_mark_good_leaves_the_cached_slots_alone(self):
        slots = [dict(self.slot), {**self.slot, 'temp': 35}]
        marked = mark_good(slots, 2, 32, 15)
        self.assertEqual([s['good'] for s in marked], [True, False])
        self.assertNotIn('good', slots[0])


class LocationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('rina', password='x')
        self.profile = Profile.objects.create(user=self.user, display_name='Rina', is_grower=True, area='Tebet')

    def test_profile_village_code_and_area_are_used(self):
        # adm4_code comes from the profile location feature; set it on the instance here
        self.user.profile.adm4_code = TEBET
        self.assertEqual(location_for_user(self.user), {'adm4': TEBET, 'name': 'Tebet', 'has_location': True})

    @override_settings(BMKG_DEFAULT_ADM4='32.76.06.1001')
    def test_default_setting_is_used_without_a_location(self):
        for user in (self.user, AnonymousUser(), None):
            with self.subTest(user=user):
                self.assertEqual(location_for_user(user), {'adm4': '32.76.06.1001', 'name': '', 'has_location': False})
        self.user.profile.adm4_code = 'not-a-code'
        self.assertFalse(location_for_user(self.user)['has_location'])

    def test_built_in_default_when_setting_is_blank(self):
        with override_settings(BMKG_DEFAULT_ADM4=''):
            self.assertEqual(location_for_user(self.user)['adm4'], '31.71.03.1001')


class ForecastForUserTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('rina', password='x')
        Profile.objects.create(user=self.user, display_name='Rina', is_grower=True, area='Tebet')

    def test_unavailable_weather_never_raises(self):
        with patch_bmkg(side_effect=requests.Timeout()):
            weather = forecast_for_user(self.user)
        self.assertFalse(weather['available'])
        self.assertEqual(weather['error'], UNAVAILABLE_MESSAGE)
        self.assertEqual(weather['source'], 'BMKG')
        self.assertEqual(weather['slots'], [])

    def test_profile_area_names_the_forecast(self):
        self.user.profile.adm4_code = TEBET
        with patch_bmkg(bmkg_payload(slots_from_now())) as remote:
            weather = forecast_for_user(self.user)
        self.assertEqual(remote.call_args.kwargs['params'], {'adm4': TEBET})
        self.assertTrue(weather['available'])
        self.assertEqual(weather['location_name'], 'Tebet')
        self.assertTrue(weather['has_location'])
        self.assertIsNotNone(weather['current'])
        self.assertTrue(weather['today'])

    def test_default_location_uses_the_bmkg_village_name(self):
        with patch_bmkg(bmkg_payload(slots_from_now(), village='Kemayoran')):
            weather = forecast_for_user(self.user)
        self.assertEqual(weather['location_name'], 'Kemayoran')
        self.assertFalse(weather['has_location'])

    def test_old_slots_are_dropped(self):
        with patch_bmkg(bmkg_payload(slots_from_now(count=3, start_hours=-12))):
            weather = forecast_for_user(self.user)
        self.assertFalse(weather['available'])
        self.assertEqual(weather['error'], UNAVAILABLE_MESSAGE)


class TemplateTagTests(TestCase):
    template = Template('{% load weather_tags %}{% weather_line %}{% user_forecast as w %}[{{ w.source }}]')

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('rina', password='x')
        Profile.objects.create(user=self.user, display_name='Rina', is_grower=True, area='Tebet')

    def render(self):
        request = RequestFactory().get('/')
        request.user = self.user
        return self.template.render(Context({'request': request}))

    def test_weather_line_shows_now_source_and_area_link(self):
        with patch_bmkg(bmkg_payload(slots_from_now(t=29, desc='Sunny'))) as remote:
            html = self.render()
        self.assertIn('29&deg;', html)
        self.assertIn('Sunny', html)
        self.assertIn('Source: <a href="https://www.bmkg.go.id/"', html)
        self.assertIn('[BMKG]', html)
        self.assertIn('Set your area in your profile to see local weather', html)
        self.assertIn('href="/profile/"', html)
        # Both tags share one lookup per request
        self.assertEqual(remote.call_count, 1)

    def test_weather_line_fallback(self):
        with patch_bmkg(side_effect=requests.ConnectionError()):
            html = self.render()
        self.assertIn('Weather is unavailable right now', html)
        self.assertIn('Source: <a', html)

    def test_area_link_is_hidden_once_a_location_is_set(self):
        self.user.profile.adm4_code = TEBET
        with patch_bmkg(bmkg_payload(slots_from_now())):
            html = self.render()
        self.assertIn('Now in Tebet', html)
        self.assertNotIn('Set your area', html)

