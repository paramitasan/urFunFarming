from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from care.models import CareSettings, CareTask
from gardens.models import Garden, Planting


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
