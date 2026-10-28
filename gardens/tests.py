from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile

from gardens.forms import PlantingForm
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

    def test_owner_garden_list_filters_by_location_and_visibility(self):
        Garden.objects.create(
            owner=self.owner,
            name='Rooftop herbs',
            location='Jakarta',
            growing_method='Hydroponics',
            is_public=True,
        )
        self.client.force_login(self.owner)

        response = self.client.get(self.mine_url, {'location': 'Jakarta', 'visibility': 'public'})

        self.assertEqual(response.context['garden_count'], 1)
        self.assertContains(response, 'Rooftop herbs')
        self.assertNotContains(response, 'Balcony garden')

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
        Planting.objects.create(
            garden=self.garden,
            crop='Lettuce',
            planting_date=date(2026, 10, 10),
        )
        self.client.force_login(self.owner)

        detail_response = self.client.get(self.detail_url)
        edit_form_response = self.client.get(self.edit_url)
        edit_response = self.client.post(self.edit_url, self.garden_data(name='Updated garden'))

        self.assertNotContains(detail_response, 'Water before noon.')
        self.assertContains(edit_form_response, 'Water before noon.')
        self.assertContains(detail_response, 'Newest planted')
        self.assertContains(detail_response, 'aria-label="Filter plants"')
        self.assertContains(detail_response, 'Planted in')
        self.assertContains(detail_response, 'Open journal')
        self.assertContains(detail_response, 'Private garden: only you can see these plants')
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

    def test_owner_routes_require_login(self):
        owner_urls = [self.mine_url, self.create_url, self.detail_url, self.edit_url, self.delete_url]
        for url in owner_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f'/login?next={url}', fetch_redirect_response=False)

    def test_only_growers_can_create_gardens(self):
        for user in (self.buyer, self.no_profile):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                self.assertEqual(self.client.get(self.create_url).status_code, 403)
                self.assertEqual(self.client.post(self.create_url, self.garden_data()).status_code, 403)

        self.assertFalse(Garden.objects.filter(name='Courtyard garden').exists())

    def test_non_owners_get_404_whatever_their_role(self):
        for user in (self.buyer, self.no_profile, self.other_owner):
            self.client.force_login(user)
            for url in (self.detail_url, self.edit_url, self.delete_url):
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 404)

    def test_owner_without_grower_role_still_manages_own_garden(self):
        Profile.objects.filter(user=self.owner).update(is_grower=False)
        self.client.force_login(self.owner)

        self.assertEqual(self.client.get(self.mine_url).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        response = self.client.post(self.edit_url, self.garden_data(name='Renamed garden'))

        self.assertRedirects(response, self.detail_url)
        self.garden.refresh_from_db()
        self.assertEqual(self.garden.name, 'Renamed garden')
        self.assertEqual(self.client.get(self.create_url).status_code, 403)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PlantingOwnerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='planting_owner', password='test-password')
        cls.other_owner = User.objects.create_user(username='other_grower', password='test-password')
        cls.buyer = User.objects.create_user(username='buyer', password='test-password')
        Profile.objects.create(user=cls.owner, display_name='Planting Owner', is_grower=True)
        Profile.objects.create(user=cls.other_owner, display_name='Other Grower', is_grower=True)
        Profile.objects.create(user=cls.buyer, display_name='Buyer', is_buyer=True)
        cls.garden = Garden.objects.create(
            owner=cls.owner,
            name='Balcony garden',
            location='Depok',
            growing_method='Container pots',
        )
        cls.other_garden = Garden.objects.create(
            owner=cls.other_owner,
            name='Rooftop garden',
            location='Jakarta',
            growing_method='Raised beds',
        )
        cls.planting = Planting.objects.create(
            garden=cls.garden,
            crop='Tomatoes',
            planting_date=date(2026, 10, 1),
        )

    def setUp(self):
        self.garden_url = reverse('gardens:detail', args=[self.garden.pk])
        self.create_url = reverse('gardens:planting_create', args=[self.garden.pk])
        self.detail_url = reverse('gardens:planting_detail', args=[self.garden.pk, self.planting.pk])
        self.edit_url = reverse('gardens:planting_edit', args=[self.garden.pk, self.planting.pk])
        self.delete_url = reverse('gardens:planting_delete', args=[self.garden.pk, self.planting.pk])

    def planting_data(self, **changes):
        data = {'name': 'Butterhead', 'crop': 'Lettuce', 'planting_date': '2026-10-12', 'growing_method': ''}
        data.update(changes)
        return data

    def test_owner_can_list_and_view_planting(self):
        self.client.force_login(self.owner)

        garden_response = self.client.get(self.garden_url)
        detail_response = self.client.get(self.detail_url)

        self.assertContains(garden_response, 'Tomatoes')
        self.assertContains(garden_response, self.detail_url)
        self.assertContains(detail_response, 'Planted 1 Oct 2026')
        self.assertContains(detail_response, 'Container pots')

    def test_owner_planting_list_filters_by_crop_and_month(self):
        Planting.objects.create(
            garden=self.garden,
            crop='Mint',
            planting_date=date(2026, 9, 20),
        )
        self.client.force_login(self.owner)

        by_crop = self.client.get(self.garden_url, {'q': 'tomato'})
        by_month = self.client.get(self.garden_url, {'month': '9'})

        self.assertEqual(by_crop.context['planting_count'], 1)
        self.assertContains(by_crop, 'Tomatoes')
        self.assertNotContains(by_crop, '>Mint<')
        self.assertEqual(by_month.context['planting_count'], 1)
        self.assertContains(by_month, 'Mint')

    def test_owner_can_create_planting_only_in_url_garden(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.create_url, self.planting_data(garden=self.other_garden.pk))

        planting = Planting.objects.get(crop='Lettuce')
        self.assertEqual(planting.garden, self.garden)
        self.assertRedirects(
            response,
            reverse('gardens:planting_detail', args=[self.garden.pk, planting.pk]),
        )

    def test_planting_form_requires_name_crop_and_date(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.create_url)

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'This field is required.', count=3, status_code=400)
        self.assertEqual(set(PlantingForm().fields), {'name', 'crop', 'planting_date', 'growing_method'})
        self.assertFalse(PlantingForm().fields['growing_method'].required)

    def test_owner_can_edit_planting(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.edit_url, self.planting_data(crop='Cherry tomatoes'))

        self.assertRedirects(response, self.detail_url)
        self.planting.refresh_from_db()
        self.assertEqual(self.planting.crop, 'Cherry tomatoes')

    def test_delete_planting_requires_post_confirmation(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.delete_url)

        self.assertContains(response, 'Delete Tomatoes?')
        self.assertTrue(Planting.objects.filter(pk=self.planting.pk).exists())
        response = self.client.post(self.delete_url)

        self.assertRedirects(response, self.garden_url)
        self.assertFalse(Planting.objects.filter(pk=self.planting.pk).exists())

    def test_other_grower_cannot_read_or_change_planting(self):
        self.client.force_login(self.other_owner)
        response = self.client.get(self.detail_url)
        self.assertContains(response, 'No access', status_code=403)
        self.assertNotContains(response, 'Tomatoes', status_code=403)
        urls = (self.edit_url, self.delete_url)

        for url in urls:
            with self.subTest(method='GET', url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
            with self.subTest(method='POST', url=url):
                self.assertEqual(self.client.post(url, self.planting_data()).status_code, 404)

        self.assertTrue(Planting.objects.filter(pk=self.planting.pk).exists())

    def test_planting_cannot_be_accessed_through_wrong_garden_url(self):
        self.client.force_login(self.owner)
        wrong_detail_url = reverse('gardens:planting_detail', args=[self.other_garden.pk, self.planting.pk])

        self.assertEqual(self.client.get(wrong_detail_url).status_code, 404)

    def test_planting_changes_require_login(self):
        for url in (self.create_url, self.edit_url, self.delete_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f'/login?next={url}', fetch_redirect_response=False)

    def test_only_growers_can_add_plants(self):
        self.client.force_login(self.buyer)

        self.assertEqual(self.client.get(self.create_url).status_code, 403)
        self.assertEqual(self.client.post(self.create_url, self.planting_data()).status_code, 403)
        self.assertFalse(Planting.objects.filter(crop='Lettuce').exists())

    def test_buyer_cannot_change_someone_elses_planting(self):
        self.client.force_login(self.buyer)

        for url in (self.edit_url, self.delete_url):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, self.planting_data()).status_code, 404)
        self.assertTrue(Planting.objects.filter(pk=self.planting.pk).exists())

    def test_growers_cannot_add_plants_to_someone_elses_garden(self):
        self.client.force_login(self.other_owner)

        response = self.client.post(self.create_url, self.planting_data())

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Planting.objects.filter(crop='Lettuce').exists())


class GardenDiscoveryViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='public_grower', password='test-password')
        cls.other_owner = User.objects.create_user(username='another_public_grower', password='test-password')
        cls.inactive_owner = User.objects.create_user(username='inactive_grower', password='test-password', is_active=False)
        Profile.objects.create(user=cls.owner, display_name='Public Grower', is_grower=True)
        Profile.objects.create(user=cls.other_owner, display_name='Another Public Grower', is_grower=True)
        Profile.objects.create(user=cls.inactive_owner, display_name='Inactive Grower', is_grower=True)
        cls.public_garden = Garden.objects.create(
            owner=cls.owner,
            name='Sunny Balcony',
            location='Depok',
            growing_method='Container pots',
            public_summary='Herbs and vegetables in the morning sun.',
            private_notes='Never show these private notes.',
            is_public=True,
        )
        cls.private_garden = Garden.objects.create(
            owner=cls.owner,
            name='Hidden Garden',
            location='Jakarta',
            growing_method='Raised beds',
            public_summary='Private summary that must not appear.',
            private_notes='Hidden private notes.',
        )
        cls.other_public_garden = Garden.objects.create(
            owner=cls.other_owner,
            name='Community Rooftop',
            location='Jakarta',
            growing_method='Raised beds',
            is_public=True,
        )
        cls.inactive_garden = Garden.objects.create(
            owner=cls.inactive_owner,
            name='Inactive Grower Garden',
            location='Bogor',
            growing_method='Hydroponics',
            is_public=True,
        )
        Planting.objects.create(garden=cls.public_garden, crop='Basil', planting_date=date(2026, 9, 20))
        Planting.objects.create(garden=cls.public_garden, crop='Tomatoes', planting_date=date(2026, 10, 1))
        Planting.objects.create(garden=cls.private_garden, crop='Private crop', planting_date=date(2026, 10, 2))

    def test_explore_shows_only_public_gardens_from_active_growers(self):
        response = self.client.get(reverse('gardens:explore'))

        self.assertContains(response, 'css/gardens.css')
        self.assertContains(response, 'Sunny Balcony')
        self.assertContains(response, 'Public Grower')
        self.assertContains(response, '2 plants')
        self.assertNotContains(response, 'Hidden Garden')
        self.assertNotContains(response, 'Inactive Grower Garden')
        self.assertNotContains(response, 'Never show these private notes.')

    def test_signed_in_grower_does_not_see_their_own_garden_in_explore(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('gardens:explore'))

        self.assertNotContains(response, 'Sunny Balcony')
        self.assertContains(response, 'Community Rooftop')

    def test_explore_search_matches_garden_crop_and_filters_by_method(self):
        url = reverse('gardens:explore')

        by_crop = self.client.get(url, {'q': 'basil'})
        by_method = self.client.get(url, {'method': 'Container pots'})
        by_location = self.client.get(url, {'location': 'Jakarta'})
        no_match = self.client.get(url, {'q': 'unlisted crop'})

        self.assertEqual(by_crop.context['garden_count'], 1)
        self.assertContains(by_crop, 'Sunny Balcony')
        self.assertEqual(by_method.context['garden_count'], 1)
        self.assertEqual(by_location.context['garden_count'], 1)
        self.assertContains(by_location, 'Community Rooftop')
        self.assertEqual(no_match.context['garden_count'], 0)
        self.assertContains(no_match, 'No gardens found')

    def test_public_detail_projects_only_approved_fields(self):
        url = reverse('gardens:public_detail', args=[self.public_garden.pk])

        response = self.client.get(url)

        self.assertContains(response, 'Herbs and vegetables in the morning sun.')
        self.assertContains(response, 'Public Grower')
        self.assertContains(response, 'Basil')
        self.assertContains(response, 'Tomatoes')
        self.assertNotContains(response, 'Never show these private notes.')
        self.assertNotContains(response, 'Hidden private notes.')
        self.assertNotIn('private_notes', response.context['garden'])
        self.assertNotContains(response, 'Filters')
        self.assertContains(response, 'Newest planted')

    def test_private_and_inactive_gardens_have_no_public_detail(self):
        private_url = reverse('gardens:public_detail', args=[self.private_garden.pk])
        inactive_url = reverse('gardens:public_detail', args=[self.inactive_garden.pk])

        self.assertEqual(self.client.get(private_url).status_code, 404)
        self.assertEqual(self.client.get(inactive_url).status_code, 404)

    def test_invalid_search_is_handled_without_server_error(self):
        response = self.client.get(reverse('gardens:explore'), {'q': 'x' * 101})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['garden_count'], 0)
        self.assertTrue(response.context['filter_form'].errors)

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GardenPrivacyRuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='rina', password='test-password')
        cls.other_grower = User.objects.create_user(username='bayu', password='test-password')
        cls.buyer = User.objects.create_user(username='sekar', password='test-password')
        Profile.objects.create(user=cls.owner, display_name='Rina', is_grower=True)
        Profile.objects.create(user=cls.other_grower, display_name='Bayu', is_grower=True)
        Profile.objects.create(user=cls.buyer, display_name='Sekar', is_buyer=True)
        cls.public_garden = Garden.objects.create(
            owner=cls.owner,
            name='Atap Hijau Tebet',
            location='Tebet, Jakarta',
            growing_method='Hydroponic',
            public_summary='Hydroponic NFT on an office rooftop.',
            private_notes='Spare key under the blue pot.',
            is_public=True,
        )
        cls.private_garden = Garden.objects.create(
            owner=cls.owner,
            name='Secret Courtyard',
            location='Kuningan, Jakarta',
            growing_method='Soil pot',
            private_notes='Neighbour waters on Sundays.',
        )
        cls.public_plant = Planting.objects.create(
            garden=cls.public_garden, crop='Butterhead lettuce', planting_date=date(2026, 9, 18),
        )
        cls.private_plant = Planting.objects.create(
            garden=cls.private_garden, crop='Hidden chili', planting_date=date(2026, 10, 1),
        )

    def plant_url(self, planting):
        return reverse('gardens:planting_detail', args=[planting.garden_id, planting.pk])

    def as_each_non_owner(self):
        # Anonymous visitor, a buyer and another grower
        yield 'anonymous'
        for user in (self.buyer, self.other_grower):
            self.client.force_login(user)
            yield user.username
        self.client.logout()

    def test_private_garden_is_404_for_everyone_but_the_owner(self):
        urls = (
            reverse('gardens:detail', args=[self.private_garden.pk]),
            reverse('gardens:public_detail', args=[self.private_garden.pk]),
        )
        for who in self.as_each_non_owner():
            for url in urls:
                with self.subTest(who=who, url=url):
                    if who == 'anonymous' and 'explore' not in url:
                        self.assertEqual(self.client.get(url).status_code, 302)
                    else:
                        self.assertEqual(self.client.get(url).status_code, 404)

    def test_private_garden_plant_shows_no_access_without_details(self):
        url = self.plant_url(self.private_plant)
        for who in self.as_each_non_owner():
            with self.subTest(who=who):
                response = self.client.get(url)
                self.assertContains(response, 'No access', status_code=403)
                self.assertNotContains(response, 'Hidden chili', status_code=403)
                self.assertNotContains(response, 'Secret Courtyard', status_code=403)

    def test_private_garden_plant_is_visible_to_owner(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.plant_url(self.private_plant))

        self.assertContains(response, 'Hidden chili')
        self.assertContains(response, reverse('gardens:detail', args=[self.private_garden.pk]))

    def test_every_plant_in_a_public_garden_is_public_and_read_only(self):
        url = self.plant_url(self.public_plant)
        edit_url = reverse('gardens:planting_edit', args=[self.public_garden.pk, self.public_plant.pk])
        delete_url = reverse('gardens:planting_delete', args=[self.public_garden.pk, self.public_plant.pk])
        for who in self.as_each_non_owner():
            with self.subTest(who=who):
                response = self.client.get(url)
                self.assertContains(response, 'Butterhead lettuce')
                self.assertNotContains(response, edit_url)
                self.assertNotContains(response, delete_url)
                self.assertContains(response, reverse('gardens:public_detail', args=[self.public_garden.pk]))

    def test_plant_of_inactive_owner_is_not_public(self):
        User.objects.filter(pk=self.owner.pk).update(is_active=False)

        response = self.client.get(self.plant_url(self.public_plant))

        self.assertContains(response, 'No access', status_code=403)

    def test_owner_is_sent_from_their_public_page_to_their_own_view(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('gardens:public_detail', args=[self.public_garden.pk]))

        self.assertRedirects(response, reverse('gardens:detail', args=[self.public_garden.pk]))

    def test_explore_never_lists_the_signed_in_users_own_gardens(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('gardens:explore'))

        self.assertNotContains(response, 'Atap Hijau Tebet')
        self.assertEqual(response.context['garden_count'], 0)

    def test_private_notes_only_appear_in_the_owners_edit_form(self):
        self.client.force_login(self.owner)
        owner_pages = (
            reverse('gardens:mine'),
            reverse('gardens:detail', args=[self.public_garden.pk]),
            reverse('gardens:detail', args=[self.private_garden.pk]),
            self.plant_url(self.public_plant),
            self.plant_url(self.private_plant),
        )
        for url in owner_pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, 'Spare key under the blue pot.')
                self.assertNotContains(response, 'Neighbour waters on Sundays.')

        edit_response = self.client.get(reverse('gardens:edit', args=[self.public_garden.pk]))
        self.assertContains(edit_response, 'Spare key under the blue pot.')

        self.client.force_login(self.buyer)
        public_pages = (
            reverse('gardens:explore'),
            reverse('gardens:public_detail', args=[self.public_garden.pk]),
            self.plant_url(self.public_plant),
        )
        for url in public_pages:
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), 'Spare key under the blue pot.')


class GardenNavigationTests(TestCase):
    HOME_ACTIVE = '<a href="/home/" data-label="Home" aria-current="page">Home</a>'
    EXPLORE_ACTIVE = '<a href="/gardens/explore/" data-label="Explore gardens" aria-current="page">Explore gardens</a>'
    SUBNAV = 'aria-label="Grower tools"'
    MY_GARDENS_ACTIVE = 'href="/gardens/mine/" aria-current="page"'

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='nav_owner', password='test-password')
        cls.visitor = User.objects.create_user(username='nav_visitor', password='test-password')
        Profile.objects.create(user=cls.owner, display_name='Nav Owner', is_grower=True)
        Profile.objects.create(user=cls.visitor, display_name='Nav Visitor', is_grower=True)
        cls.garden = Garden.objects.create(
            owner=cls.owner, name='Rooftop', location='Tebet', growing_method='Hydroponic', is_public=True,
        )
        cls.planting = Planting.objects.create(garden=cls.garden, crop='Pak choy', planting_date=date(2026, 10, 9))

    def test_owner_pages_highlight_home_and_show_my_gardens_subnav(self):
        self.client.force_login(self.owner)
        urls = (
            reverse('gardens:mine'),
            reverse('gardens:create'),
            reverse('gardens:detail', args=[self.garden.pk]),
            reverse('gardens:edit', args=[self.garden.pk]),
            reverse('gardens:planting_create', args=[self.garden.pk]),
            reverse('gardens:planting_detail', args=[self.garden.pk, self.planting.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, self.HOME_ACTIVE, html=True)
                self.assertNotContains(response, self.EXPLORE_ACTIVE, html=True)
                self.assertContains(response, self.SUBNAV, count=1)
                self.assertContains(response, self.MY_GARDENS_ACTIVE)

    def test_public_pages_highlight_explore_without_subnav(self):
        self.client.force_login(self.visitor)
        urls = (
            reverse('gardens:explore'),
            reverse('gardens:public_detail', args=[self.garden.pk]),
            reverse('gardens:planting_detail', args=[self.garden.pk, self.planting.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, self.EXPLORE_ACTIVE, html=True)
                self.assertNotContains(response, self.HOME_ACTIVE, html=True)
                self.assertNotContains(response, self.SUBNAV)

    def test_logged_out_visitors_see_explore_highlighted(self):
        response = self.client.get(reverse('gardens:public_detail', args=[self.garden.pk]))

        self.assertContains(response, self.EXPLORE_ACTIVE, html=True)
        self.assertNotContains(response, self.SUBNAV)

    def test_home_page_keeps_its_subnav_with_nothing_active(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('main:home'))

        self.assertContains(response, self.HOME_ACTIVE, html=True)
        self.assertContains(response, self.SUBNAV, count=1)
        self.assertNotContains(response, self.MY_GARDENS_ACTIVE)


class GardenDesignDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='design_owner', password='test-password')
        cls.visitor = User.objects.create_user(username='design_visitor', password='test-password')
        Profile.objects.create(user=cls.owner, display_name='Rina', is_grower=True, area='Tebet')
        Profile.objects.create(user=cls.visitor, display_name='Bayu', is_grower=True)
        cls.garden = Garden.objects.create(
            owner=cls.owner,
            name='Balcony rack, Tebet',
            location='Tebet, Jakarta',
            growing_method='Hydroponic',
            public_summary='Small NFT rack on a west-facing balcony.',
            is_public=True,
        )
        Garden.objects.create(owner=cls.owner, name='Rooftop beds', location='Tebet, Jakarta', growing_method='Soil')
        cls.pak_choy = Planting.objects.create(
            garden=cls.garden, name='Pak choy', crop='Leafy greens', planting_date=date(2026, 10, 9),
        )
        cls.chili = Planting.objects.create(
            garden=cls.garden, name='Red chili', crop='Fruiting veg',
            planting_date=date(2026, 9, 15), growing_method='Soil pot',
        )

    def test_planting_falls_back_to_crop_and_garden_method(self):
        old_style = Planting.objects.create(garden=self.garden, crop='Tomatoes', planting_date=date(2026, 10, 1))

        self.assertEqual(old_style.display_name, 'Tomatoes')
        self.assertEqual(old_style.method, 'Hydroponic')
        self.assertEqual(self.chili.display_name, 'Red chili')
        self.assertEqual(self.chili.method, 'Soil pot')

    def test_day_number_counts_days_since_planting(self):
        today = timezone.localdate()
        planting = Planting.objects.create(garden=self.garden, crop='Mint', planting_date=today - timedelta(days=18))
        planned = Planting.objects.create(garden=self.garden, crop='Basil', planting_date=today + timedelta(days=3))

        self.assertEqual(planting.day_number, 18)
        self.assertEqual(planned.day_number, 0)

    def test_owner_detail_filters_by_each_plants_own_method(self):
        self.client.force_login(self.owner)
        url = reverse('gardens:detail', args=[self.garden.pk])

        everything = self.client.get(url)
        hydroponic = self.client.get(url, {'method': 'Hydroponic'})
        soil_pot = self.client.get(url, {'method': 'Soil pot'})

        self.assertEqual(everything.context['methods'], ['Hydroponic', 'Soil pot'])
        self.assertEqual([p.name for p in hydroponic.context['plantings']], ['Pak choy'])
        self.assertEqual([p.name for p in soil_pot.context['plantings']], ['Red chili'])
        self.assertContains(everything, 'Day ')
        self.assertContains(everything, 'More actions for Pak choy')
        self.assertContains(everything, reverse('gardens:planting_edit', args=[self.garden.pk, self.pak_choy.pk]))

    def test_plant_search_matches_name_and_crop(self):
        self.client.force_login(self.owner)
        url = reverse('gardens:detail', args=[self.garden.pk])

        by_name = self.client.get(url, {'q': 'pak'})
        by_crop = self.client.get(url, {'q': 'fruiting'})

        self.assertEqual(by_name.context['planting_count'], 1)
        self.assertEqual(by_crop.context['planting_count'], 1)
        self.assertContains(by_crop, 'Red chili')

    def test_my_gardens_shows_visibility_counts_and_owner_menu(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('gardens:mine'))

        self.assertEqual(
            response.context['visibility_options'],
            [('', 'All', 2), ('public', 'Public', 1), ('private', 'Private', 1)],
        )
        self.assertContains(response, 'YOUR GROWING SPACES')
        self.assertContains(response, reverse('gardens:edit', args=[self.garden.pk]))
        self.assertContains(response, reverse('gardens:delete', args=[self.garden.pk]))
        self.assertContains(response, 'Private')

    def test_my_gardens_search_matches_plant_names(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('gardens:mine'), {'q': 'pak choy'})

        self.assertEqual(response.context['garden_count'], 1)
        self.assertContains(response, 'Balcony rack, Tebet')

    def test_explore_card_shows_owner_and_no_owner_menu(self):
        self.client.force_login(self.visitor)

        response = self.client.get(reverse('gardens:explore'))

        self.assertContains(response, 'by Rina')
        self.assertContains(response, 'member since')
        self.assertNotContains(response, 'More actions for')
        self.assertNotContains(response, 'Rooftop beds')

    def test_visitor_detail_has_about_the_grower_and_no_owner_actions(self):
        self.client.force_login(self.visitor)

        response = self.client.get(reverse('gardens:public_detail', args=[self.garden.pk]))

        self.assertContains(response, 'aria-label="About the grower"')
        self.assertContains(response, 'Grower · Tebet')
        self.assertContains(response, 'Public garden by Rina')
        self.assertContains(response, f"{reverse('marketplace:index')}?grower=design_owner")
        self.assertContains(response, 'Pak choy')
        self.assertNotContains(response, 'More actions for')
        self.assertNotContains(response, reverse('gardens:planting_create', args=[self.garden.pk]))
        self.assertNotContains(response, reverse('gardens:planting_edit', args=[self.garden.pk, self.pak_choy.pk]))
