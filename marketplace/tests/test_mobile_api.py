from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from marketplace.dates import jakarta_today
from marketplace.models import HarvestListing
from marketplace.tests.helpers import MarketplaceCase
from marketplace.tests.test_weather_seed import weather_payload
from marketplace.weather import WeatherUnavailable
from weather.testing import patch_bmkg


class MobileMarketplaceTests(MarketplaceCase):
    def setUp(self):
        self.api = APIClient(enforce_csrf_checks=True)
        self.collection = reverse('marketplace_api:listings')
        self.mine = reverse('marketplace_api:mine')
        self.detail = reverse('marketplace_api:detail', args=[self.listing.id])

    def login(self, user):
        reply = self.api.post('/api/auth/login/', {'username': user.username, 'password': 'garden-test-password'}, format='json')
        self.assertEqual(reply.status_code, 200, reply.content)
        self.api.credentials(HTTP_AUTHORIZATION='Token ' + reply.json()['token'])

    def test_public_filters_pagination_and_private_contacts(self):
        self.make_listing(is_available=False)
        self.make_listing(available_from=jakarta_today()+timedelta(days=1))
        for i in range(6):
            self.make_listing(title=f'Mint {i}', price=0)
        result = self.api.get(self.collection).json()
        self.assertEqual((result['count'], result['page'], result['pages'], len(result['results'])), (7, 1, 2, 6))
        self.assertEqual(len(self.api.get(self.collection, {'page': 2}).json()['results']), 1)
        self.assertEqual(self.api.get(self.collection, {'q': 'mint', 'category': 'herbs', 'price_type': 'free', 'city': 'Depok'}).json()['count'], 6)
        self.assertEqual(self.api.get(self.collection, {'availability': 'any'}).json()['count'], 8)
        self.assertEqual(self.api.get(self.collection, {'city': 'invalid'}).status_code, 400)
        self.assertNotIn('contact', self.api.get(self.detail).json())
        self.assertEqual(self.api.get(self.mine).status_code, 401)
        self.login(self.buyer)
        self.assertEqual(self.api.get(self.detail).json()['contact']['email'], self.profile.contact_email)
        entry = self.api.get(self.collection).json()['results'][0]
        self.assertNotIn('contact', entry)
        self.assertFalse(entry['can_manage'])

    def test_grower_creation_and_ownership(self):
        self.assertEqual(self.api.post(self.collection, self.data(), format='json').status_code, 401)
        self.login(self.buyer)
        self.assertEqual(self.api.post(self.collection, self.data(), format='json').status_code, 403)
        self.api.credentials()
        self.login(self.owner)
        res = self.api.post(self.collection, self.data(owner=self.other.pk, is_demo=True), format='json')
        self.assertEqual(res.status_code, 201, res.content)
        row = HarvestListing.objects.get(pk=res.json()['id'])
        self.assertEqual(row.owner, self.owner)
        self.assertFalse(row.is_demo)
        self.assertTrue(res.json()['can_manage'])
        self.assertEqual(res.json()['price_unit_label'], '500 g')
        self.assertEqual(self.api.put(self.detail, self.data(title='Replaced'), format='json').json()['title'], 'Replaced')

    def test_private_mine_and_owner_lifecycle(self):
        private = self.make_listing(is_available=False, title='Paused basil')
        other_url = reverse('marketplace_api:detail', args=[private.id])
        self.assertEqual(self.api.get(other_url).status_code, 404)
        self.login(self.other)
        self.assertEqual(self.api.get(self.mine).json()['results'], [])
        self.assertEqual(self.api.get(other_url).status_code, 404)
        self.assertEqual(self.api.patch(self.detail, {'title': 'New'}, format='json').status_code, 403)
        self.assertEqual(self.api.delete(self.detail).status_code, 403)
        self.api.credentials()
        self.login(self.owner)
        self.assertEqual(self.api.get(self.mine).json()['count'], 2)
        self.profile.is_grower = False
        self.profile.save()
        self.assertEqual(self.api.patch(other_url, {'is_available': True}, format='json').status_code, 200)
        self.assertEqual(self.api.delete(other_url).status_code, 204)
        self.assertEqual(self.api.get(other_url).status_code, 404)

    def test_patch_validates_complete_listing_and_keeps_original(self):
        self.login(self.owner)
        for body, field in [({'quantity': '0'}, 'quantity'), ({'price_quantity': 0}, 'price_quantity'),
                            ({'available_until': (jakarta_today()-timedelta(days=1)).isoformat()}, 'available_until'),
                            ({'image_url': 'ftp://example.org/plant.jpg'}, 'image_url')]:
            response = self.api.patch(self.detail, body, format='json')
            self.assertEqual(response.status_code, 400, response.content)
            self.assertIn(field, response.json())
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, 6)
        self.assertEqual(self.api.patch(self.detail, {'quantity': 0, 'is_available': False}, format='json').status_code, 200)

    def test_invalid_token_and_website_session_are_not_mobile_logins(self):
        self.api.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assertEqual(self.api.get(self.mine).status_code, 401)
        self.api.credentials()
        self.api.force_login(self.owner)
        self.assertNotIn('contact', self.api.get(self.detail).json())
        self.assertEqual(self.api.post(self.collection, self.data(), format='json').status_code, 401)

    def test_pickup_reuses_bmkg_validation_and_handles_outage(self):
        cache.clear()
        self.addCleanup(cache.clear)
        url = reverse('marketplace_api:weather', args=[self.listing.id])
        query = {'date': (jakarta_today()+timedelta(days=1)).isoformat(), 'start_time': '08:00', 'end_time': '18:00', 'max_rain': '1', 'max_temperature': '35'}
        with patch_bmkg(weather_payload()) as remote:
            self.assertEqual(self.api.get(url, {**query, 'max_rain': '-1'}).status_code, 400)
            remote.assert_not_called()
            result = self.api.get(url, query).json()
        self.assertEqual(result['source'], 'BMKG')
        self.assertEqual(result['timezone'], 'Asia/Jakarta')
        self.assertEqual([slot['time'][11:16] for slot in result['results']], ['08:00', '17:00'])
        with patch('marketplace.api_views.forecast', side_effect=WeatherUnavailable('Forecast unavailable')):
            self.assertEqual(self.api.get(url, query).status_code, 503)
