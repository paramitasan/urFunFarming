from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile

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


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GardenOwnerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='garden_owner', password='test-password')
        cls.other_owner = User.objects.create_user(username='other_grower', password='test-password')
        cls.buyer = User.objects.create_user(username='buyer', password='test-password')
        cls.no_profile = User.objects.create_user(username='no_profile', password='test-password')
        Profile.objects.create(user=cls.owner, display_name='Garden Owner', is_grower=True)
        Profile.objects.create(user=cls.other_owner, display_name='Other Grower', is_grower=True)
        Profile.objects.create(user=cls.buyer, display_name='Buyer', is_buyer=True)
        cls.garden = Garden.objects.create(
            owner=cls.owner,
            name='Balcony garden',
            location='Depok',
            growing_method='Container pots',
            private_notes='Water before noon.',
        )
        cls.other_garden = Garden.objects.create(
            owner=cls.other_owner,
            name='Rooftop garden',
            location='Jakarta',
            growing_method='Raised beds',
        )

    def setUp(self):
        self.mine_url = reverse('gardens:mine')
        self.create_url = reverse('gardens:create')
        self.detail_url = reverse('gardens:detail', args=[self.garden.pk])
        self.edit_url = reverse('gardens:edit', args=[self.garden.pk])
        self.delete_url = reverse('gardens:delete', args=[self.garden.pk])

    def garden_data(self, **changes):
        data = {
            'name': 'Courtyard garden',
            'location': 'Beji',
            'growing_method': 'Soil beds',
            'public_summary': 'Vegetables grown in a shared courtyard.',
            'private_notes': 'Check the soil moisture.',
            'is_public': 'on',
        }
        data.update(changes)
        return data

    def test_owner_can_list_only_their_gardens(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.mine_url)

        self.assertContains(response, 'Balcony garden')
        self.assertNotContains(response, 'Rooftop garden')

    def test_owner_is_assigned_by_server_and_can_create_garden(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.create_url, self.garden_data(owner=self.other_owner.pk))

        garden = Garden.objects.get(name='Courtyard garden')
        self.assertEqual(garden.owner, self.owner)
        self.assertTrue(garden.is_public)
        self.assertRedirects(response, reverse('gardens:detail', args=[garden.pk]))

    def test_invalid_garden_form_is_rendered_with_errors(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.create_url, self.garden_data(name=''))

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'This field is required.', status_code=400)

    def test_empty_create_post_shows_required_field_errors(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.create_url)

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'This field is required.', status_code=400)

    def test_owner_can_view_and_update_private_garden_details(self):
        self.client.force_login(self.owner)

        detail_response = self.client.get(self.detail_url)
        edit_response = self.client.post(self.edit_url, self.garden_data(name='Updated garden'))

        self.assertContains(detail_response, 'Water before noon.')
        self.assertRedirects(edit_response, self.detail_url)
        self.garden.refresh_from_db()
        self.assertEqual(self.garden.name, 'Updated garden')

    def test_other_grower_cannot_view_edit_or_delete_garden(self):
        self.client.force_login(self.other_owner)

        for method, url in (
            (self.client.get, self.detail_url),
            (self.client.get, self.edit_url),
            (self.client.get, self.delete_url),
            (self.client.post, self.edit_url),
            (self.client.post, self.delete_url),
        ):
            with self.subTest(method=method.__name__, url=url):
                self.assertEqual(method(url, self.garden_data()).status_code, 404)

        self.assertTrue(Garden.objects.filter(pk=self.garden.pk).exists())

    def test_delete_requires_confirmation_and_post(self):
        self.client.force_login(self.owner)

        confirm_response = self.client.get(self.delete_url)

        self.assertContains(confirm_response, 'This also deletes the plantings')
        self.assertTrue(Garden.objects.filter(pk=self.garden.pk).exists())
        response = self.client.post(self.delete_url)

        self.assertRedirects(response, self.mine_url)
        self.assertFalse(Garden.objects.filter(pk=self.garden.pk).exists())

    def test_owner_routes_require_login_and_grower_role(self):
        detail_other_url = reverse('gardens:detail', args=[self.other_garden.pk])
        owner_urls = [self.mine_url, self.create_url, self.detail_url, self.edit_url, self.delete_url]
        for url in owner_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login/', response.url)

        for user in (self.buyer, self.no_profile):
            self.client.force_login(user)
            for url in owner_urls + [detail_other_url]:
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)