from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from gardens.models import Garden, Planting


class GardenModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='grower', password='test-password')
        self.garden = Garden.objects.create(
            owner=self.owner,
            name='Balcony garden',
            location='Depok',
            growing_method='Container pots',
        )

    def test_garden_is_private_by_default(self):
        self.assertFalse(self.garden.is_public)
        self.assertEqual(self.garden.private_notes, '')

    def test_garden_is_owned_by_grower(self):
        self.assertEqual(self.owner.gardens.get(), self.garden)
        self.assertEqual(str(self.garden), 'Balcony garden')

    def test_planting_belongs_to_garden(self):
        planting = Planting.objects.create(
            garden=self.garden,
            crop='Tomatoes',
            planting_date=date(2026, 10, 1),
        )

        self.assertEqual(self.garden.plantings.get(), planting)
        self.assertEqual(str(planting), 'Tomatoes in Balcony garden')