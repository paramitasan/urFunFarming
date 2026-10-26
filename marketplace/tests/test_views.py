import json
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.test import Client
from django.urls import reverse

from marketplace.dates import jakarta_today
from marketplace.models import HarvestListing
from marketplace.tests.helpers import MarketplaceCase


class MarketplaceBrowsingTests(MarketplaceCase):
    def test_public_catalog_renders_shared_theme_and_real_records(self):
        response = self.client.get(reverse('marketplace:index'))
        self.assertContains(response, 'Harvest Marketplace')
        self.assertContains(response, 'Fresh basil')
        self.assertContains(response, 'bootstrap-grid.min.css')
        self.assertContains(response, 'marketplace.js')
        self.assertContains(response, 'aria-current="page"')
        self.assertNotContains(response, self.profile.phone)
        self.assertNotContains(response, self.profile.contact_email)

    def test_ajax_fragment_avoids_duplicate_page_shell(self):
        response = self.client.get(reverse('marketplace:index'), HTTP_X_REQUESTED_WITH='fetch')
        self.assertContains(response, 'harvest-card')
        self.assertNotContains(response, '<!DOCTYPE')
        response = self.client.get(reverse('marketplace:index'), HTTP_HX_REQUEST='true')
        self.assertNotContains(response, '<html')

    def test_catalog_filters_combine(self):
        self.make_listing(title='Free mint', price=Decimal('0'))
        self.make_listing(title='Paid carrot', category='vegetables', area='Tebet', city='Jakarta')
        response = self.client.get(reverse('marketplace:index'), {'category': 'herbs', 'city': 'Depok', 'area': 'Beji', 'price_type': 'free', 'q': 'mint', 'max_price': '0'})
        self.assertEqual(response.context['listing_count'], 1)
        self.assertContains(response, 'Free mint')
        self.assertNotContains(response, 'Paid carrot')

    def test_paid_maximum_price_grower_and_case_insensitive_search(self):
        self.make_listing(owner=self.other, title='Basil from another grower', price=Decimal('50000'))
        response = self.client.get(reverse('marketplace:listings_json'), {'price_type': 'paid', 'max_price': '15000', 'grower': self.owner.username, 'q': 'BASIL'})
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(response.json()['results'][0]['id'], str(self.listing.pk))

    def test_paused_expired_and_inactive_grower_records_stay_out_of_public_browsing(self):
        self.make_listing(title='Paused offer', is_available=False)
        self.make_listing(title='Expired offer', available_from=jakarta_today()-timedelta(days=3), available_until=jakarta_today()-timedelta(days=1))
        self.other.is_active = False
        self.other.save()
        self.make_listing(owner=self.other, title='Inactive grower offer')
        response = self.client.get(reverse('marketplace:listings_json'))
        self.assertEqual(response.json()['count'], 1)

    def test_any_time_shows_future_available_harvests(self):
        self.make_listing(title='Future herbs', available_from=jakarta_today()+timedelta(days=2))
        now = self.client.get(reverse('marketplace:listings_json')).json()
        any_time = self.client.get(reverse('marketplace:listings_json'), {'availability': 'any'}).json()
        self.assertEqual(now['count'], 1)
        self.assertEqual(any_time['count'], 2)

    def test_stable_pagination_and_all_sort_orders(self):
        for i in range(9):
            self.make_listing(title=f'Vegetable {i}', price=Decimal(i))
        for sort, expected in [('price_asc', 'Vegetable 0'), ('price_desc', 'Fresh basil'), ('title', 'Fresh basil')]:
            with self.subTest(sort=sort):
                data = self.client.get(reverse('marketplace:listings_json'), {'sort': sort}).json()
                self.assertEqual(data['results'][0]['title'], expected)
                self.assertEqual(len(data['results']), 6)
                self.assertEqual(data['count'], 10)
        first = self.client.get(reverse('marketplace:listings_json')).json()
        second = self.client.get(reverse('marketplace:listings_json'), {'page': 2}).json()
        self.assertFalse({x['id'] for x in first['results']} & {x['id'] for x in second['results']})
        for bad_page in ['bad', '-1', '999999999999999']:
            self.assertEqual(self.client.get(reverse('marketplace:listings_json'), {'page': bad_page}).status_code, 200)

    def test_invalid_filters_are_reported_without_server_errors(self):
        for query in [{'category': 'invalid'}, {'max_price': 'NaN'}, {'q': 'x'*121}, {'availability': 'invalid'}]:
            with self.subTest(query=query):
                self.assertEqual(self.client.get(reverse('marketplace:listings_json'), query).status_code, 400)
                response = self.client.get(reverse('marketplace:index'), query)
                self.assertContains(response, 'Please check your filters.')
                self.assertEqual(response.context['listing_count'], 0)

    def test_empty_catalog_is_useful(self):
        response = self.client.get(reverse('marketplace:index'), {'q': 'unfindable'})
        self.assertContains(response, 'No harvests match these filters')

    def test_contacts_are_private_in_html_and_json(self):
        urls = [self.listing.get_absolute_url(), reverse('marketplace:listing_json', args=[self.listing.pk])]
        for url in urls:
            response = self.client.get(url)
            self.assertNotContains(response, self.profile.phone)
            self.assertNotContains(response, self.profile.contact_email)
            self.assertIn('private', response['Cache-Control'])
            self.assertIn('no-store', response['Cache-Control'])
        self.client.force_login(self.buyer)
        for url in urls:
            response = self.client.get(url)
            self.assertContains(response, self.profile.phone)
            self.assertContains(response, self.profile.contact_email)
        public_list = self.client.get(reverse('marketplace:listings_json'))
        self.assertNotContains(public_list, self.profile.phone)

    def test_hidden_record_is_visible_only_to_owner(self):
        hidden = self.make_listing(is_available=False)
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(hidden.get_absolute_url()), 'Paused')

    def test_detail_handles_profile_without_contact_and_missing_ids(self):
        self.client.force_login(self.buyer)
        offer = self.make_listing(owner=self.no_profile, image_url='https://example.com/image.png', available_until=None)
        self.assertContains(self.client.get(offer.get_absolute_url()), 'added contact details yet')
        data = self.client.get(reverse('marketplace:listing_json', args=[offer.pk])).json()
        self.assertEqual(data['contact'], {'phone': '', 'email': ''})
        self.assertIsNone(data['available_until'])
        self.assertEqual(self.client.get(reverse('marketplace:detail', args=[uuid4()])).status_code, 404)
        self.assertEqual(self.client.get('/marketplace/not-a-uuid/').status_code, 404)
        missing_api = self.client.get(reverse('marketplace:listing_json', args=[uuid4()]))
        self.assertEqual(missing_api.status_code, 404)
        self.assertEqual(missing_api.json()['status'], 'error')

    def test_user_content_is_escaped_and_landing_uses_same_database(self):
        self.listing.title = '<script>alert("test")</script>'
        self.listing.description = '<img src=x onerror=alert(1)>'
        self.listing.save()
        response = self.client.get(self.listing.get_absolute_url())
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(')
        self.assertNotContains(response, '<img src=x')
        home = self.client.get(reverse('main:show_main'))
        self.assertContains(home, self.listing.get_absolute_url())
        self.assertContains(home, '1 harvest listing from')
        self.assertContains(self.client.get(reverse('main:filter_listings'), {'category': 'herbs'}), '&lt;script&gt;')
        self.assertNotContains(self.client.get(reverse('main:filter_listings'), {'category': 'free'}), '&lt;script&gt;')


class MarketplaceWriteTests(MarketplaceCase):
    def setUp(self):
        self.create_url = reverse('marketplace:create')
        self.api_url = reverse('marketplace:listings_json')
        self.edit_url = reverse('marketplace:edit', args=[self.listing.pk])
        self.delete_url = reverse('marketplace:delete', args=[self.listing.pk])
        self.api_detail = reverse('marketplace:listing_json', args=[self.listing.pk])

    def test_anonymous_membership_requirements_and_method_guards(self):
        for url in [self.create_url, self.edit_url, self.delete_url, reverse('marketplace:mine')]:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(self.api_url, self.data()).status_code, 401)
        self.assertEqual(self.client.post(self.create_url, self.data(), HTTP_X_REQUESTED_WITH='fetch').status_code, 401)
        self.assertEqual(self.client.patch(self.api_detail, '{}', content_type='application/json').status_code, 401)
        self.assertEqual(self.client.post(reverse('marketplace:index')).status_code, 405)
        self.assertEqual(self.client.post(self.listing.get_absolute_url()).status_code, 405)
        self.assertEqual(self.client.delete(self.api_url).status_code, 405)

    def test_only_growers_can_create(self):
        for user in (self.buyer, self.no_profile):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertContains(self.client.get(self.create_url), 'Update my roles', status_code=403)
                self.assertEqual(self.client.post(self.api_url, self.data()).status_code, 403)

    def test_owner_is_assigned_server_side_and_demo_flag_cannot_be_forged(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.create_url, self.data(owner=self.other.pk, is_demo=True))
        self.assertEqual(response.status_code, 302)
        listing = HarvestListing.objects.get(title='Fresh tomatoes')
        self.assertEqual(listing.owner, self.owner)
        self.assertFalse(listing.is_demo)
        self.assertEqual(listing.price_quantity, Decimal('500'))
        self.assertRedirects(response, listing.get_absolute_url())

    def test_create_form_uses_existing_profile_area_and_city(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.create_url)
        self.assertEqual(response.context['form'].initial['area'], 'Beji')
        self.assertEqual(response.context['form'].initial['city'], 'Depok')

    def test_invalid_html_and_ajax_creation_preserves_database(self):
        self.client.force_login(self.owner)
        before = HarvestListing.objects.count()
        response = self.client.post(self.create_url, self.data(quantity='0'))
        self.assertEqual(response.status_code, 400)
        response = self.client.post(self.create_url, self.data(price='-1'), HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 400)
        self.assertIn('price', response.json()['errors'])
        self.assertEqual(HarvestListing.objects.count(), before)

    def test_ajax_create_update_and_delete_success(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.create_url, self.data(), HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 201)
        pk = response.json()['listing']['id']
        response = self.client.post(reverse('marketplace:edit', args=[pk]), self.data(title='Updated tomatoes'), HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['listing']['title'], 'Updated tomatoes')
        response = self.client.post(reverse('marketplace:delete', args=[pk]), HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(HarvestListing.objects.filter(pk=pk).exists())

    def test_get_edit_and_delete_are_read_only_then_post_deletes(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.edit_url), 'Edit your harvest')
        self.assertContains(self.client.get(self.delete_url), 'Delete this listing?')
        self.assertTrue(HarvestListing.objects.filter(pk=self.listing.pk).exists())
        response = self.client.post(self.delete_url)
        self.assertRedirects(response, reverse('marketplace:mine'))
        self.assertFalse(HarvestListing.objects.filter(pk=self.listing.pk).exists())

    def test_other_users_cannot_read_management_forms_or_modify_an_offer(self):
        self.client.force_login(self.other)
        for url in [self.edit_url, self.delete_url]:
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, self.data()).status_code, 404)
        for method in ('put', 'patch', 'delete'):
            response = getattr(self.client, method)(self.api_detail, json.dumps(self.data()), content_type='application/json')
            self.assertEqual(response.status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, 'Fresh basil')

    def test_my_listings_cannot_be_switched_to_another_owner(self):
        self.make_listing(owner=self.other, title='Other private listing', is_available=False)
        self.make_listing(title='My paused listing', is_available=False)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('marketplace:mine'), {'owner': self.other.pk})
        self.assertEqual(response.context['listing_count'], 2)
        self.assertContains(response, 'My paused listing')
        self.assertNotContains(response, 'Other private listing')
        self.assertNotContains(self.client.get(reverse('marketplace:mine'), HTTP_X_REQUESTED_WITH='fetch'), '<html')

    def test_owners_can_manage_existing_offers_after_disabling_grower_role(self):
        self.profile.is_grower = False
        self.profile.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.edit_url, self.data()).status_code, 302)

    def test_json_create_defaults_and_partial_update(self):
        self.client.force_login(self.owner)
        payload = self.data()
        for field in ['available_from', 'is_available', 'price_quantity', 'city']:
            payload.pop(field)
        response = self.client.post(self.api_url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        pk = response.json()['listing']['id']
        detail = reverse('marketplace:listing_json', args=[pk])
        response = self.client.patch(detail, json.dumps({'title': 'Revised offer', 'owner': self.other.pk}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        item = HarvestListing.objects.get(pk=pk)
        self.assertEqual(item.owner, self.owner)
        self.assertEqual(item.title, 'Revised offer')
        self.assertEqual(item.quantity, Decimal('1500'))
        self.assertTrue(item.is_available)
        self.assertEqual(self.client.delete(detail).status_code, 200)

    def test_json_full_update_and_invalid_or_non_object_payloads(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.put(self.api_detail, json.dumps(self.data()), content_type='application/json').status_code, 200)
        for payload in ['{broken', '[]', 'null', '"text"']:
            with self.subTest(payload=payload):
                response = self.client.post(self.api_url, payload, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['status'], 'error')
        self.assertEqual(self.client.put(self.api_detail, '{}', content_type='application/json').status_code, 400)

    def test_csrf_is_required_for_html_and_json_writes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.create_url, self.data()).status_code, 403)
        self.assertEqual(client.post(self.api_url, json.dumps(self.data()), content_type='application/json').status_code, 403)
        client.get(self.create_url)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.api_url, json.dumps(self.data()), content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_login_returns_to_marketplace_and_refuses_external_redirects(self):
        for ajax in [False, True]:
            url = reverse('accounts:login_ajax' if ajax else 'accounts:login')
            for target, expected in [(self.listing.get_absolute_url(), self.listing.get_absolute_url()),
                                     ('https://evil.example/path', reverse('main:home')),
                                     ('//evil.example/path', reverse('main:home'))]:
                with self.subTest(ajax=ajax, target=target):
                    self.client.logout()
                    response = self.client.post(url, {'username': self.owner.username, 'password': 'garden-test-password', 'next': target})
                    if ajax:
                        self.assertEqual(response.json()['redirect'], expected)
                    else:
                        self.assertEqual(response.url, expected)
