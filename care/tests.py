from datetime import date, datetime, time, timedelta
from decimal import Decimal

import requests

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from care.models import CareSettings, CareTask
from care.planning import NO_FORECAST, best_times, check_data, today_card, weather_check
from gardens.models import Garden, Planting
from weather.services import JAKARTA
from weather.testing import bmkg_payload, patch_bmkg, slots_from_now


def make_planting(owner, crop='Tomato'):
    garden = Garden.objects.create(owner=owner, name='Balcony rack', location='Tebet', growing_method='Pots')
    return Planting.objects.create(garden=garden, crop=crop, planting_date=date(2026, 9, 1))


class CareTaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('rina', password='x')
        self.planting = make_planting(self.user)

    def test_new_tasks_start_as_to_do_with_an_optional_time(self):
        task = CareTask.objects.create(owner=self.user, planting=self.planting, title='Water the tomatoes', target_date=date(2026, 10, 28))
        self.assertEqual(task.status, CareTask.Status.TODO)
        self.assertEqual(task.activity, CareTask.Activity.WATER)
        self.assertIsNone(task.target_time)
        self.assertEqual(str(task), 'Water the tomatoes (To do)')

    def test_choices_match_the_design(self):
        self.assertEqual(CareTask.Activity.labels, ['Water', 'Fertilize', 'Prune', 'Check pH', 'Harvest', 'Other'])
        self.assertEqual(CareTask.Status.labels, ['To do', 'In progress', 'Completed'])

    def test_soonest_target_comes_first(self):
        later = CareTask.objects.create(owner=self.user, planting=self.planting, title='Later', target_date=date(2026, 10, 30))
        evening = CareTask.objects.create(owner=self.user, planting=self.planting, title='Evening', target_date=date(2026, 10, 28), target_time=time(18))
        morning = CareTask.objects.create(owner=self.user, planting=self.planting, title='Morning', target_date=date(2026, 10, 28), target_time=time(7))
        self.assertEqual(list(CareTask.objects.exclude(target_time=None)), [morning, evening])
        self.assertEqual(CareTask.objects.last(), later)

    def test_someone_elses_planting_is_rejected(self):
        other = User.objects.create_user('budi', password='x')
        task = CareTask(owner=other, planting=self.planting, title='Sneaky', target_date=date(2026, 10, 28))
        with self.assertRaises(ValidationError) as error:
            task.full_clean()
        self.assertIn('planting', error.exception.message_dict)


class CareSettingsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('rina', password='x')

    def test_defaults_and_one_row_per_user(self):
        settings_row = CareSettings.for_user(self.user)
        self.assertEqual(
            (settings_row.max_rain_mm, settings_row.max_temp_c, settings_row.max_wind_kmh),
            (Decimal('2'), Decimal('32'), Decimal('15')),
        )
        self.assertEqual(CareSettings.for_user(self.user), settings_row)
        self.assertEqual(CareSettings.objects.count(), 1)

    def test_a_slot_is_good_only_within_all_three_limits(self):
        settings_row = CareSettings.for_user(self.user)
        slot = {'rain_mm': 2, 'temp': 32, 'wind_kmh': 15}
        self.assertTrue(settings_row.is_good(slot))
        self.assertFalse(settings_row.is_good({**slot, 'rain_mm': 3.5}))
        self.assertFalse(settings_row.is_good({**slot, 'temp': 33}))
        self.assertFalse(settings_row.is_good({**slot, 'wind_kmh': 20}))

    def test_limits_cannot_be_negative(self):
        settings_row = CareSettings(user=self.user, max_rain_mm=Decimal('-1'))
        with self.assertRaises(ValidationError):
            settings_row.full_clean()


class CareViewTestCase(TestCase):
    """Logged-in grower with one planting; BMKG is always mocked."""

    def setUp(self):
        cache.clear()
        patcher = patch_bmkg(bmkg_payload(slots_from_now()))
        self.remote = patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user('rina', password='pass-12345')
        Profile.objects.create(user=self.user, display_name='Rina', is_grower=True, area='Tebet')
        self.planting = make_planting(self.user, crop='Cherry tomato')
        self.client.force_login(self.user)

    def make_task(self, owner=None, planting=None, **fields):
        values = {'title': 'Water the tomatoes', 'target_date': date(2026, 10, 28), **fields}
        return CareTask.objects.create(owner=owner or self.user, planting=planting or self.planting, **values)

    def task_data(self, **changes):
        return {
            'activity': 'water', 'planting': self.planting.pk, 'title': 'Water the tomatoes',
            'target_date': '2026-10-28', 'target_time': '07:00', 'notes': 'Skip if it rains.', 'status': 'todo',
            **changes,
        }


class CareCrudTests(CareViewTestCase):
    def test_create_saves_for_the_logged_in_grower(self):
        response = self.client.post(reverse('care:create'), self.task_data())
        self.assertRedirects(response, reverse('care:index'))
        task = CareTask.objects.get()
        self.assertEqual((task.owner, task.planting, task.target_time), (self.user, self.planting, time(7)))
        self.assertEqual(task.status, CareTask.Status.TODO)

    def test_blank_title_is_built_from_activity_and_plant(self):
        self.client.post(reverse('care:create'), self.task_data(title='', activity='check_ph'))
        self.assertEqual(CareTask.objects.get().title, 'Check pH Cherry tomato')

    def test_invalid_post_shows_the_form_again(self):
        response = self.client.post(reverse('care:create'), self.task_data(target_date=''))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CareTask.objects.exists())

    def test_edit_and_delete(self):
        task = self.make_task()
        response = self.client.post(reverse('care:edit', args=[task.pk]), self.task_data(title='Water twice', status='in_progress'))
        self.assertRedirects(response, reverse('care:index'))
        task.refresh_from_db()
        self.assertEqual((task.title, task.status), ('Water twice', 'in_progress'))
        self.assertContains(self.client.get(reverse('care:delete', args=[task.pk])), 'Water twice')
        self.assertRedirects(self.client.post(reverse('care:delete', args=[task.pk])), reverse('care:index'))
        self.assertFalse(CareTask.objects.exists())

    def test_status_change_keeps_the_chosen_filter(self):
        task = self.make_task()
        url = reverse('care:status', args=[task.pk])
        response = self.client.post(url, {'status': 'completed', 'next': '/care/?status=all'})
        self.assertRedirects(response, '/care/?status=all', fetch_redirect_response=False)
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        # An unknown status changes nothing, and outside redirects are refused
        self.client.post(url, {'status': 'done'})
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        response = self.client.post(url, {'status': 'todo', 'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('care:index'))
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_thresholds_are_saved_per_user(self):
        data = {'max_rain_mm': '1', 'max_temp_c': '30', 'max_wind_kmh': '10', 'next': '/care/new/'}
        response = self.client.post(reverse('care:settings'), data)
        self.assertRedirects(response, '/care/new/', fetch_redirect_response=False)
        saved = CareSettings.for_user(self.user)
        self.assertEqual((saved.max_rain_mm, saved.max_temp_c, saved.max_wind_kmh), (Decimal('1'), Decimal('30'), Decimal('10')))
        self.client.post(reverse('care:settings'), {**data, 'max_rain_mm': '-3'})
        self.assertEqual(CareSettings.for_user(self.user).max_rain_mm, Decimal('1'))


class CareListTests(CareViewTestCase):
    def test_status_filter_counts_and_default_to_do(self):
        for status, count in (('todo', 3), ('in_progress', 2), ('completed', 1)):
            for i in range(count):
                self.make_task(title=f'{status} {i}', status=status)
        response = self.client.get(reverse('care:index'))
        filters = {value: count for value, label, count in response.context['status_filters']}
        self.assertEqual(filters, {'todo': 3, 'in_progress': 2, 'completed': 1, 'all': 6})
        self.assertEqual(response.context['status'], 'todo')
        self.assertEqual(len(response.context['tasks']), 3)
        self.assertEqual(len(self.client.get(reverse('care:index'), {'status': 'all'}).context['tasks']), 6)
        self.assertEqual(len(self.client.get(reverse('care:index'), {'status': 'completed'}).context['tasks']), 1)
        # An edited URL falls back to the defaults instead of failing
        response = self.client.get(reverse('care:index'), {'status': 'nope', 'sort': 'nope'})
        self.assertEqual((response.context['status'], response.context['sort']), ('todo', 'soonest'))

    def test_sorting(self):
        late = self.make_task(title='Late', target_date=date(2026, 10, 30))
        early = self.make_task(title='Early', target_date=date(2026, 10, 27))

        def tasks(sort):
            return list(self.client.get(reverse('care:index'), {'sort': sort}).context['tasks'])

        self.assertEqual(tasks('soonest'), [early, late])
        self.assertEqual(tasks('latest'), [late, early])

    def test_list_only_shows_my_tasks(self):
        other = User.objects.create_user('budi', password='x')
        Profile.objects.create(user=other, display_name='Budi', is_grower=True)
        self.make_task(owner=other, planting=make_planting(other), title='Budi task')
        self.make_task(title='Rina task')
        response = self.client.get(reverse('care:index'), {'status': 'all'})
        self.assertContains(response, 'Rina task')
        self.assertNotContains(response, 'Budi task')


class CarePermissionTests(CareViewTestCase):
    def test_login_is_required(self):
        self.client.logout()
        for url in (reverse('care:index'), reverse('care:create')):
            response = self.client.get(url)
            self.assertRedirects(response, f'/login?next={url}', fetch_redirect_response=False)

    def test_another_users_task_is_a_404(self):
        other = User.objects.create_user('budi', password='x')
        task = self.make_task(owner=other, planting=make_planting(other))
        for name in ('care:edit', 'care:delete'):
            self.assertEqual(self.client.get(reverse(name, args=[task.pk])).status_code, 404)
            self.assertEqual(self.client.post(reverse(name, args=[task.pk]), self.task_data()).status_code, 404)
        self.assertEqual(self.client.post(reverse('care:status', args=[task.pk]), {'status': 'completed'}).status_code, 404)
        task.refresh_from_db()
        self.assertEqual((task.title, task.status), ('Water the tomatoes', 'todo'))

    def test_buyer_only_account_is_blocked(self):
        buyer = User.objects.create_user('sari', password='x')
        Profile.objects.create(user=buyer, display_name='Sari', is_buyer=True)
        self.client.force_login(buyer)
        for url in (reverse('care:index'), reverse('care:create')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, 'Add the grower role', status_code=403)
        self.assertEqual(self.client.post(reverse('care:create'), self.task_data()).status_code, 403)
        self.assertFalse(CareTask.objects.exists())

    def test_planting_dropdown_only_lists_my_plantings(self):
        other = User.objects.create_user('budi', password='x')
        theirs = make_planting(other, crop='Mango')
        response = self.client.get(reverse('care:create'))
        self.assertEqual(list(response.context['form'].fields['planting'].queryset), [self.planting])
        self.assertContains(response, 'Cherry tomato · Balcony rack, Tebet')
        self.assertNotContains(response, 'Mango')
        # Posting someone else's planting anyway is rejected
        response = self.client.post(reverse('care:create'), self.task_data(planting=theirs.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn('planting', response.context['form'].errors)
        self.assertFalse(CareTask.objects.exists())


def slot(moment, temp=28, rain=0.0, wind=5, kind='sun', description='Sunny'):
    return {'time': moment, 'temp': temp, 'rain_mm': rain, 'wind_kmh': wind, 'humidity': 70, 'description': description, 'kind': kind}


def day_at(day, hour):
    return datetime.combine(day, time(hour), tzinfo=JAKARTA)


def no_weather():
    return {'available': False, 'error': 'Weather is unavailable right now', 'slots': [], 'today': []}


class CarePlanningTests(TestCase):
    """The weather card line, the best-times list and the form's weather check."""

    def setUp(self):
        self.user = User.objects.create_user('rina', password='x')
        self.settings = CareSettings.for_user(self.user)
        self.tomorrow = timezone.localdate() + timedelta(days=1)

    def weather(self, slots, today=None):
        return {'available': True, 'error': '', 'slots': slots, 'today': today if today is not None else slots}

    def test_today_card_when_every_slot_is_within_the_limits(self):
        slots = [slot(day_at(self.tomorrow, h)) for h in (6, 9, 12)]
        card = today_card(self.weather(slots), self.settings)
        self.assertEqual([s['good'] for s in card['slots']], [True, True, True])
        self.assertEqual(card['summary'], 'No rain expected today. Every slot today is within your limits.')
        self.assertFalse(card['rain'])

    def test_today_card_names_the_rain_and_the_dry_windows(self):
        slots = [slot(day_at(self.tomorrow, h)) for h in (6, 9, 12)]
        slots.append(slot(day_at(self.tomorrow, 15), rain=5, kind='rain', description='Rain'))
        slots += [slot(day_at(self.tomorrow, h), kind='moon', description='Clear') for h in (18, 21)]
        card = today_card(self.weather(slots), self.settings)
        self.assertEqual([s['good'] for s in card['slots']], [True, True, True, False, True, True])
        self.assertEqual(card['summary'], 'Rain expected around 15:00. Outdoor tasks fit best 06:00-15:00 or from 18:00.')
        self.assertTrue(card['rain'])

    def test_today_card_light_rain_inside_the_limit_stays_green(self):
        slots = [slot(day_at(self.tomorrow, 9)), slot(day_at(self.tomorrow, 12), rain=1, kind='rain', description='Light Rain')]
        card = today_card(self.weather(slots), self.settings)
        self.assertTrue(card['slots'][1]['good'])
        self.assertEqual(card['summary'], 'Light rain around 12:00, within your rain limit. Every slot today is within your limits.')

    def test_today_card_with_no_weather(self):
        self.assertEqual(today_card(no_weather(), self.settings), {'slots': [], 'summary': '', 'rain': False})

    def test_best_times_are_daytime_windows_one_per_day(self):
        day2 = self.tomorrow + timedelta(days=1)
        slots = [slot(day_at(self.tomorrow, h)) for h in (0, 3, 6, 9, 12, 15, 18, 21)]
        slots[4]['temp'] = 35  # 12:00 too hot, so the day splits into two windows
        slots += [slot(day_at(day2, h), temp=31) for h in (6, 9)]
        slots.append(slot(day_at(day2, 12), wind=30))
        windows = best_times(self.weather(slots), self.settings)
        self.assertEqual([w['label'] for w in windows], [
            f'{self.tomorrow:%a} 06:00-12:00', f'{self.tomorrow:%a} 15:00-18:00', f'{day2:%a} 06:00-12:00',
        ])
        self.assertEqual((windows[0]['date'], windows[0]['time'], windows[0]['temp']), (self.tomorrow, time(6), 28))
        # Slots from 18:00 and the night ones (00:00, 03:00, 21:00) never count as a best time
        self.assertTrue(all(6 <= w['start'].hour <= 17 for w in windows))

    def test_best_times_are_empty_without_weather_or_good_slots(self):
        self.assertEqual(best_times(no_weather(), self.settings), [])
        self.assertEqual(best_times(self.weather([slot(day_at(self.tomorrow, 9), rain=9)]), self.settings), [])

    def test_weather_check_messages(self):
        slots = [slot(day_at(self.tomorrow, 6), kind='cloud', description='Cloudy'), slot(day_at(self.tomorrow, 9), temp=34, wind=20)]
        weather = self.weather(slots)
        self.assertIsNone(weather_check(weather, self.settings, None, None))
        good = weather_check(weather, self.settings, self.tomorrow, time(7))
        self.assertTrue(good['good'])
        self.assertEqual(good['text'], f'{self.tomorrow:%A} morning looks good: cloudy, 28°, 0 mm rain, wind 5 km/h. Meets all your thresholds.')
        bad = weather_check(weather, self.settings, self.tomorrow, time(10))
        self.assertFalse(bad['good'])
        self.assertIn('Over your temperature and wind limit.', bad['text'])
        whole_day = weather_check(weather, self.settings, self.tomorrow, None)
        self.assertEqual(whole_day['text'], f'{self.tomorrow:%A} has good times from 06:00. Pick a time to check it.')
        self.assertEqual(weather_check(weather, self.settings, self.tomorrow + timedelta(days=5), time(9))['text'], NO_FORECAST)
        down = weather_check(no_weather(), self.settings, self.tomorrow, time(9))
        self.assertEqual((down['good'], down['text']), (None, 'Weather is unavailable right now.'))

    def test_check_data_has_one_entry_per_slot(self):
        slots = [slot(day_at(self.tomorrow, 6)), slot(day_at(self.tomorrow, 9), rain=4)]
        data = check_data(self.weather(slots), self.settings)
        self.assertEqual([d['good'] for d in data], [True, False])
        self.assertEqual(data[0]['start'], day_at(self.tomorrow, 6).isoformat())
        self.assertEqual(check_data(no_weather(), self.settings), [])


class CareWeatherPageTests(CareViewTestCase):
    """Every Plant care page that shows weather goes through the shared service and credits BMKG."""

    SOURCE = 'Source: <a href="https://www.bmkg.go.id/"'

    def test_list_uses_the_profile_location_and_marks_green_slots(self):
        self.user.profile.adm4_code = '31.74.01.1001'
        self.user.profile.save()
        self.remote.return_value.json.return_value = bmkg_payload(slots_from_now(count=4, t=28, tp=0) + slots_from_now(count=2, start_hours=11, t=35))
        response = self.client.get(reverse('care:index'))
        self.assertEqual(self.remote.call_args.kwargs['params'], {'adm4': '31.74.01.1001'})
        self.assertContains(response, 'Weather today in Tebet')
        self.assertContains(response, self.SOURCE)
        self.assertContains(response, 'Green hours: rain up to 2 mm, up to 32 °C, wind up to 15 km/h.')
        self.assertTrue(response.context['card']['slots'][0]['good'])
        self.assertNotContains(response, 'Set your area in your profile')
        self.assertNotContains(response, 'Open-Meteo')

    def test_list_without_a_location_links_to_the_profile(self):
        response = self.client.get(reverse('care:index'))
        self.assertContains(response, 'Set your area in your profile to see local weather')
        self.assertContains(response, 'href="/profile/#location"')
        self.assertEqual(self.remote.call_args.kwargs['params'], {'adm4': '31.71.03.1001'})

    def test_each_weather_page_shows_the_fallback_when_bmkg_is_down(self):
        task = self.make_task()
        self.remote.side_effect = requests.ConnectionError('down')
        for name, url in (('list', reverse('care:index')), ('new', reverse('care:create')), ('edit', reverse('care:edit', args=[task.pk]))):
            with self.subTest(page=name):
                cache.clear()
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Weather is unavailable right now')
                self.assertContains(response, self.SOURCE)
        self.assertContains(self.client.get(reverse('care:index')), 'Water the tomatoes')

    def test_each_weather_page_calls_the_service_once_per_request(self):
        task = self.make_task()
        for url in (reverse('care:index'), reverse('care:create'), reverse('care:edit', args=[task.pk])):
            cache.clear()
            self.remote.reset_mock()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.remote.call_count, 1, url)
            self.assertContains(response, self.SOURCE)

    def test_form_lists_best_times_and_marks_the_chosen_one(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.remote.return_value.json.return_value = bmkg_payload([{'time': day_at(tomorrow, h), 't': 27, 'tp': 0, 'ws': 4, 'hu': 70} for h in (6, 9, 12)])
        response = self.client.get(reverse('care:create'))
        self.assertContains(response, 'Best times in the next 3 days')
        self.assertContains(response, f'{tomorrow:%a} 06:00-15:00')
        self.assertFalse(response.context['best_times'][0]['selected'])
        chosen = self.client.get(reverse('care:create'), {'date': tomorrow.isoformat(), 'time': '06:00'})
        self.assertTrue(chosen.context['best_times'][0]['selected'])
        self.assertContains(chosen, 'aria-current="true"')
        self.assertContains(chosen, 'Meets all your thresholds')

    def test_form_without_plantings_points_to_my_gardens(self):
        self.planting.garden.delete()
        response = self.client.get(reverse('care:create'))
        self.assertContains(response, 'Add a planting first')
        self.assertContains(response, reverse('gardens:mine'))

    def test_thresholds_card_shows_whole_numbers(self):
        response = self.client.get(reverse('care:create'))
        for value in ('2', '32', '15'):
            self.assertContains(response, f'value="{value}"')


class CarePageStateTests(CareViewTestCase):
    def test_delete_page_shows_the_dialog_over_the_list(self):
        task = self.make_task(target_date=timezone.localdate())
        response = self.client.get(reverse('care:delete', args=[task.pk]))
        self.assertContains(response, 'Delete this task?')
        self.assertContains(response, '&ldquo;Water the tomatoes&rdquo;, due today, will be removed.')
        self.assertContains(response, 'role="alertdialog"')
        self.assertContains(response, 'Plant care tasks')

    def test_empty_states(self):
        self.assertContains(self.client.get(reverse('care:index')), 'No tasks yet')
        self.make_task(status='completed')
        response = self.client.get(reverse('care:index'), {'status': 'todo'})
        self.assertContains(response, 'No tasks with this status')
        self.assertContains(response, '?status=all')
