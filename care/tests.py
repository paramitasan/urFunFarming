import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from care import planning
from care.forms import CareTaskForm
from care.models import CareTask, WeatherPreference
from gardens.models import Garden, Planting
from marketplace.weather import WeatherUnavailable

AJAX = {'HTTP_X_REQUESTED_WITH': 'fetch'}


def fake_forecast(day, hours=((6, 26.0, 80, 0.0), (12, 35.0, 55, 0.0), (15, 29.0, 95, 6.0))):
    """A forecast built by hand, so no test ever reaches the network."""
    return {
        'slots': [
            {'time': datetime.combine(day, time(hour)), 'temperature': temp, 'humidity': humid, 'rain': rain}
            for hour, temp, humid, rain in hours
        ],
        'fetched_at': 'test',
    }


class CareBaseTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='owner-pass-2026')
        Profile.objects.create(user=self.owner, display_name='Owner', is_grower=True)
        self.other = User.objects.create_user('other', password='other-pass-2026')
        Profile.objects.create(user=self.other, display_name='Other', is_grower=True)
        self.buyer = User.objects.create_user('buyer', password='buyer-pass-2026')
        Profile.objects.create(user=self.buyer, display_name='Buyer', is_grower=False, is_buyer=True)

        self.garden = Garden.objects.create(
            owner=self.owner, name='Rooftop', location='Depok', growing_method='Hydroponics'
        )
        self.planting = Planting.objects.create(
            garden=self.garden, name='Cherry tomato', crop='Tomato', planting_date=date(2026, 9, 1)
        )
        self.today = timezone.localdate()
        # No test may depend on the weather service being reachable.
        forecast_patch = patch('care.planning.forecast', return_value=fake_forecast(self.today))
        forecast_patch.start()
        self.addCleanup(forecast_patch.stop)

        self.task = CareTask.objects.create(
            owner=self.owner, planting=self.planting, activity=CareTask.Activity.WATERING,
            planned_for=self.today + timedelta(days=1), planned_time=time(6, 30), notes='Private note',
        )


class CareTaskModelTest(CareBaseTest):
    def test_str_names_activity_and_plant(self):
        self.assertIn('Watering', str(self.task))
        self.assertIn('Cherry tomato', str(self.task))

    def test_completed_at_follows_is_done(self):
        self.assertIsNone(self.task.completed_at)
        self.task.is_done = True
        self.task.save()
        self.assertIsNotNone(self.task.completed_at)

        self.task.is_done = False
        self.task.save()
        self.assertIsNone(self.task.completed_at)

    def test_overdue_only_while_open(self):
        past = CareTask.objects.create(
            owner=self.owner, planting=self.planting, planned_for=self.today - timedelta(days=1)
        )
        self.assertTrue(past.is_overdue)
        past.is_done = True
        past.save()
        self.assertFalse(past.is_overdue)

    def test_a_task_cannot_point_at_someone_elses_plant(self):
        foreign_garden = Garden.objects.create(
            owner=self.other, name='Theirs', location='Bogor', growing_method='Soil'
        )
        foreign_planting = Planting.objects.create(
            garden=foreign_garden, name='Basil', crop='Basil', planting_date=date(2026, 9, 1)
        )
        task = CareTask(owner=self.owner, planting=foreign_planting, planned_for=self.today)
        with self.assertRaises(ValidationError):
            task.full_clean()

    def test_tasks_come_back_in_planned_order(self):
        later = CareTask.objects.create(
            owner=self.owner, planting=self.planting, planned_for=self.today + timedelta(days=5)
        )
        earlier = CareTask.objects.create(
            owner=self.owner, planting=self.planting, planned_for=self.today - timedelta(days=5)
        )
        self.assertEqual(list(CareTask.objects.all()), [earlier, self.task, later])


class WeatherPreferenceTest(CareBaseTest):
    def test_defaults_are_created_once(self):
        first = WeatherPreference.for_user(self.owner)
        second = WeatherPreference.for_user(self.owner)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.city, 'Depok')

    def test_accepts_only_inside_every_limit(self):
        preference = WeatherPreference.for_user(self.owner)
        preference.max_rain_mm = Decimal('1.0')
        preference.max_temperature_c = Decimal('32.0')
        preference.max_humidity_percent = 85

        self.assertTrue(preference.accepts({'rain': 0.0, 'temperature': 28.0, 'humidity': 70}))
        self.assertFalse(preference.accepts({'rain': 5.0, 'temperature': 28.0, 'humidity': 70}))
        self.assertFalse(preference.accepts({'rain': 0.0, 'temperature': 40.0, 'humidity': 70}))
        self.assertFalse(preference.accepts({'rain': 0.0, 'temperature': 28.0, 'humidity': 99}))


class PlanningTest(CareBaseTest):
    def setUp(self):
        super().setUp()
        self.preference = WeatherPreference.for_user(self.owner)
        self.day = self.today + timedelta(days=1)
        self.data = fake_forecast(self.day)

    def test_verdict_without_a_date(self):
        self.assertEqual(planning.verdict(self.data, self.preference, None)['state'], 'none')

    def test_verdict_when_the_service_is_down(self):
        result = planning.verdict(None, self.preference, self.day, time(6))
        self.assertEqual(result['state'], 'unknown')

    def test_verdict_for_a_good_hour(self):
        result = planning.verdict(self.data, self.preference, self.day, time(6))
        self.assertEqual(result['state'], 'good')
        self.assertIn('26 degrees', result['text'])

    def test_verdict_names_the_limit_that_broke(self):
        result = planning.verdict(self.data, self.preference, self.day, time(15))
        self.assertEqual(result['state'], 'poor')
        self.assertIn('rain', result['text'])
        self.assertIn('humidity', result['text'])

    def test_verdict_for_an_hour_the_forecast_does_not_reach(self):
        result = planning.verdict(self.data, self.preference, self.day, time(23))
        self.assertEqual(result['state'], 'unknown')

    def test_verdict_for_a_whole_day(self):
        result = planning.verdict(self.data, self.preference, self.day)
        self.assertEqual(result['state'], 'good')
        self.assertIn('06:00', result['text'])

    def test_verdict_for_a_day_where_nothing_works(self):
        bad = fake_forecast(self.day, hours=((9, 38.0, 99, 9.0),))
        self.assertEqual(planning.verdict(bad, self.preference, self.day)['state'], 'poor')

    def test_suggestions_only_offer_future_hours_inside_the_limits(self):
        past = fake_forecast(self.today - timedelta(days=1))
        self.assertEqual(planning.suggestions(past, self.preference), [])

        future = planning.suggestions(self.data, self.preference)
        self.assertEqual([slot['time'].hour for slot in future], [6])

    def test_load_forecast_returns_none_when_the_service_fails(self):
        with patch('care.planning.forecast', side_effect=WeatherUnavailable('down')):
            self.assertIsNone(planning.load_forecast(self.preference))


class CareAccessTest(CareBaseTest):
    def test_anonymous_visitors_are_sent_to_the_login_page(self):
        response = self.client.get(reverse('care:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])

    def test_buyers_without_the_grower_role_get_403(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('care:index')).status_code, 403)
        self.assertEqual(self.client.get(reverse('care:create')).status_code, 403)

    def test_another_grower_cannot_reach_the_task(self):
        self.client.force_login(self.other)
        for url in [
            reverse('care:edit', args=[self.task.pk]),
            reverse('care:delete', args=[self.task.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(reverse('care:toggle_done', args=[self.task.pk])).status_code, 404)

    def test_the_list_shows_only_your_own_tasks(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('care:index'), {'show': 'all'})
        self.assertNotContains(response, 'Private note')


class CareFormTest(CareBaseTest):
    def test_the_plant_dropdown_only_offers_your_own_plants(self):
        foreign_garden = Garden.objects.create(
            owner=self.other, name='Theirs', location='Bogor', growing_method='Soil'
        )
        foreign = Planting.objects.create(
            garden=foreign_garden, name='Basil', crop='Basil', planting_date=date(2026, 9, 1)
        )
        form = CareTaskForm(user=self.owner)
        self.assertIn(self.planting, form.fields['planting'].queryset)
        self.assertNotIn(foreign, form.fields['planting'].queryset)

    def test_posting_someone_elses_plant_is_rejected(self):
        foreign_garden = Garden.objects.create(
            owner=self.other, name='Theirs', location='Bogor', growing_method='Soil'
        )
        foreign = Planting.objects.create(
            garden=foreign_garden, name='Basil', crop='Basil', planting_date=date(2026, 9, 1)
        )
        form = CareTaskForm(
            data={'planting': foreign.pk, 'activity': 'watering', 'planned_for': '2026-11-02'},
            user=self.owner,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('planting', form.errors)

    def test_malformed_dates_and_times_do_not_crash_the_page(self):
        """A typo in the date used to raise ValidationError out of the context builder."""
        self.client.force_login(self.owner)
        for bad_date in ['31-02-2026', 'tomorrow', '2026-13-45']:
            response = self.client.post(reverse('care:create'), {
                'planting': self.planting.pk, 'activity': 'watering',
                'planned_for': bad_date, 'planned_time': '', 'notes': '',
            })
            self.assertEqual(response.status_code, 400)
            self.assertContains(response, 'Enter a valid date', status_code=400)

        response = self.client.post(reverse('care:create'), {
            'planting': self.planting.pk, 'activity': 'watering',
            'planned_for': self.today.isoformat(), 'planned_time': '25:99', 'notes': '',
        })
        self.assertEqual(response.status_code, 400)

    def test_a_task_needs_a_date(self):
        form = CareTaskForm(
            data={'planting': self.planting.pk, 'activity': 'watering', 'planned_for': ''},
            user=self.owner,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('planned_for', form.errors)


class CareCrudTest(CareBaseTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.valid = {
            'planting': self.planting.pk,
            'activity': 'pruning',
            'planned_for': (self.today + timedelta(days=2)).isoformat(),
            'planned_time': '07:00',
            'notes': 'Cut the side shoots',
        }

    def test_create_adds_a_task_for_the_signed_in_grower(self):
        response = self.client.post(reverse('care:create'), self.valid)
        self.assertRedirects(response, reverse('care:index'))
        created = CareTask.objects.get(activity='pruning')
        self.assertEqual(created.owner, self.owner)

    def test_create_with_a_missing_date_redisplays_the_form(self):
        response = self.client.post(reverse('care:create'), {**self.valid, 'planned_for': ''})
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, 'care/form.html')
        self.assertEqual(CareTask.objects.filter(activity='pruning').count(), 0)

    def test_edit_changes_the_task(self):
        response = self.client.post(reverse('care:edit', args=[self.task.pk]), self.valid)
        self.assertRedirects(response, reverse('care:index'))
        self.task.refresh_from_db()
        self.assertEqual(self.task.activity, 'pruning')

    def test_delete_asks_before_removing(self):
        response = self.client.get(reverse('care:delete', args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CareTask.objects.filter(pk=self.task.pk).exists())

        self.client.post(reverse('care:delete', args=[self.task.pk]))
        self.assertFalse(CareTask.objects.filter(pk=self.task.pk).exists())

    def test_toggle_done_flips_both_ways(self):
        self.client.post(reverse('care:toggle_done', args=[self.task.pk]))
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)

        self.client.post(reverse('care:toggle_done', args=[self.task.pk]))
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_done)

    def test_toggle_done_refuses_get(self):
        self.assertEqual(self.client.get(reverse('care:toggle_done', args=[self.task.pk])).status_code, 405)


class CareFilterTest(CareBaseTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.overdue = CareTask.objects.create(
            owner=self.owner, planting=self.planting, activity='pruning',
            planned_for=self.today - timedelta(days=3),
        )
        self.finished = CareTask.objects.create(
            owner=self.owner, planting=self.planting, activity='harvesting',
            planned_for=self.today + timedelta(days=4), is_done=True,
        )

    def shown(self, **params):
        response = self.client.get(reverse('care:index'), params)
        return list(response.context['tasks'])

    def test_open_is_the_default(self):
        self.assertCountEqual(self.shown(), [self.task, self.overdue])

    def test_each_filter_narrows_the_list(self):
        self.assertCountEqual(self.shown(show='all'), [self.task, self.overdue, self.finished])
        self.assertEqual(self.shown(show='done'), [self.finished])
        self.assertEqual(self.shown(show='overdue'), [self.overdue])
        self.assertEqual(self.shown(activity='harvesting', show='all'), [self.finished])

    def test_an_unknown_filter_value_falls_back_to_the_default(self):
        self.assertCountEqual(self.shown(show='nonsense'), [self.task, self.overdue])

    def test_sorting_turns_the_list_around(self):
        soonest = self.shown(show='all', sort='soonest')
        latest = self.shown(show='all', sort='latest')
        self.assertEqual(soonest, list(reversed(latest)))

    def test_the_counts_cover_every_bucket(self):
        counts = self.client.get(reverse('care:index')).context['counts']
        self.assertEqual(counts['all'], 3)
        self.assertEqual(counts['open'], 2)
        self.assertEqual(counts['done'], 1)
        self.assertEqual(counts['overdue'], 1)


class CareAjaxTest(CareBaseTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def test_the_list_comes_back_as_json_for_fetch(self):
        response = self.client.get(reverse('care:index'), {'show': 'all'}, **AJAX)
        self.assertEqual(response['Content-Type'], 'application/json')
        payload = json.loads(response.content)
        self.assertEqual(payload['status'], 'success')
        self.assertIn('Cherry tomato', payload['html'])
        self.assertEqual(payload['counts']['all'], 1)

    def test_toggle_done_answers_with_the_new_state(self):
        response = self.client.post(reverse('care:toggle_done', args=[self.task.pk]), **AJAX)
        payload = json.loads(response.content)
        self.assertTrue(payload['is_done'])
        self.assertEqual(payload['pk'], self.task.pk)

    def test_saving_limits_returns_the_fresh_outlook(self):
        with patch('care.planning.forecast', return_value=fake_forecast(self.today)):
            response = self.client.post(reverse('care:limits'), {
                'city': 'Jakarta', 'max_rain_mm': '0.5',
                'max_temperature_c': '30', 'max_humidity_percent': '80',
            }, **AJAX)
        payload = json.loads(response.content)
        self.assertEqual(payload['status'], 'success')
        self.assertIn('state', payload['outlook'])
        self.assertEqual(WeatherPreference.for_user(self.owner).city, 'Jakarta')

    def test_bad_limits_come_back_as_field_errors(self):
        response = self.client.post(reverse('care:limits'), {
            'city': 'Jakarta', 'max_rain_mm': '999',
            'max_temperature_c': '30', 'max_humidity_percent': '80',
        }, **AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertIn('max_rain_mm', json.loads(response.content)['errors'])

    def test_creating_through_fetch_returns_201(self):
        response = self.client.post(reverse('care:create'), {
            'planting': self.planting.pk, 'activity': 'watering',
            'planned_for': (self.today + timedelta(days=1)).isoformat(),
            'planned_time': '', 'notes': '',
        }, **AJAX)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.content)['status'], 'success')

    def test_an_invalid_create_through_fetch_returns_400_with_errors(self):
        response = self.client.post(reverse('care:create'), {
            'planting': self.planting.pk, 'activity': 'watering', 'planned_for': '',
        }, **AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertIn('planned_for', json.loads(response.content)['errors'])

    def test_the_weather_check_judges_a_chosen_time(self):
        day = self.today + timedelta(days=1)
        with patch('care.planning.forecast', return_value=fake_forecast(day)):
            response = self.client.get(reverse('care:weather_check'), {
                'date': day.isoformat(), 'time': '06:00',
            }, **AJAX)
        self.assertEqual(json.loads(response.content)['verdict']['state'], 'good')

    def test_the_weather_check_survives_nonsense_input(self):
        response = self.client.get(reverse('care:weather_check'), {'date': 'xx', 'time': '99:99'}, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['verdict']['state'], 'none')

    def test_a_buyer_gets_403_from_the_json_endpoints_too(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('care:weather_check'), **AJAX).status_code, 403)
        self.assertEqual(self.client.post(reverse('care:limits'), **AJAX).status_code, 403)
