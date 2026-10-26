from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from marketplace.dates import jakarta_today
from marketplace.forms import ListingForm, PickupWeatherForm
from marketplace.models import HarvestListing, number_label, rupiah
from marketplace.tests.helpers import MarketplaceCase


class HarvestModelTests(MarketplaceCase):
    def test_price_and_quantity_units_stay_distinct(self):
        self.assertEqual(self.listing.price_label, 'Rp12.000')
        self.assertEqual(self.listing.price_unit_label, '2 bunches')
        self.assertEqual(self.listing.quantity_label, '6 bunches')
        self.assertEqual(rupiah(Decimal('1000.50')), 'Rp1.000,50')
        self.assertEqual(rupiah(Decimal('0')), 'Free')
        self.assertEqual(number_label(Decimal('0.50')), '0.5')
        self.listing.unit = 'g'
        self.assertEqual(self.listing.price_unit_label, '2 g')

    def test_title_url_and_grower_use_shared_profile(self):
        self.assertEqual(str(self.listing), 'Fresh basil')
        self.assertIn(str(self.listing.pk), self.listing.get_absolute_url())
        self.assertEqual(self.listing.grower_name, 'Ayu Grower')
        self.assertEqual(self.listing.grower_initials, 'AG')

    def test_grower_without_profile_has_safe_fallback(self):
        listing = self.make_listing(owner=self.no_profile)
        self.assertEqual(listing.grower_name, 'no_profile')
        self.assertEqual(listing.grower_initials, 'NO')

    def test_availability_labels_and_visibility(self):
        self.assertEqual(self.listing.status_label, 'Available')
        self.listing.price = Decimal('0')
        self.assertEqual(self.listing.status_label, 'Free to collect')
        self.listing.available_from += timedelta(days=1)
        self.assertTrue(self.listing.status_label.startswith('From '))
        self.listing.available_until = jakarta_today()-timedelta(days=1)
        self.assertEqual(self.listing.status_label, 'Ended')
        self.listing.is_available = False
        self.assertEqual(self.listing.status_label, 'Paused')

    def test_database_rejects_negative_prices_and_available_zero_stock(self):
        for changes in ({'price': Decimal('-1')}, {'quantity': 0}, {'price_quantity': 0}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                HarvestListing.objects.filter(pk=self.listing.pk).update(**changes)

    def test_database_rejects_reversed_dates(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            HarvestListing.objects.filter(pk=self.listing.pk).update(available_until=jakarta_today()-timedelta(days=1))

    def test_model_validation_attaches_actionable_errors(self):
        self.listing.available_until = jakarta_today()-timedelta(days=1)
        self.listing.quantity = Decimal('0')
        with self.assertRaises(ValidationError) as caught:
            self.listing.clean()
        self.assertIn('available_until', caught.exception.message_dict)
        self.assertIn('quantity', caught.exception.message_dict)

    def test_can_pause_an_empty_listing(self):
        self.listing.quantity = Decimal('0')
        self.listing.is_available = False
        self.listing.full_clean()
        self.listing.save()
        self.assertNotIn(self.listing, HarvestListing.objects.public())


class HarvestFormTests(MarketplaceCase):
    def test_valid_free_offer_and_optional_end_date(self):
        form = ListingForm(self.data(price='0', available_until=''))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['price'], Decimal('0'))

    def test_invalid_fields_fail_with_field_errors(self):
        for field, value in [('title', '   '), ('description', ''), ('quantity', '-1'), ('quantity', '0'),
                             ('price', '-1'), ('price', 'NaN'), ('price_quantity', '0'),
                             ('category', 'forged'), ('unit', 'truck'), ('city', 'Atlantis'),
                             ('image_url', 'javascript:alert(1)'), ('image_url', 'ftp://example.com/a.jpg')]:
            with self.subTest(field=field, value=value):
                form = ListingForm(self.data(**{field: value}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_dates_and_precision_are_validated(self):
        for changes, expected in [({'available_until': '1999-01-01'}, 'available_until'),
                                  ({'quantity': '1.001'}, 'quantity'), ({'title': 'x'*121}, 'title'),
                                  ({'description': 'x'*2001}, 'description')]:
            with self.subTest(changes=changes):
                form = ListingForm(self.data(**changes))
                self.assertFalse(form.is_valid())
                self.assertIn(expected, form.errors)

    def test_optional_http_photo_link_is_accepted(self):
        form = ListingForm(self.data(image_url='https://example.com/harvest.jpg'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_owner_and_demo_status_are_not_editable_form_fields(self):
        form = ListingForm(self.data(owner=self.other.pk, is_demo=True))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn('owner', form.cleaned_data)
        self.assertNotIn('is_demo', form.cleaned_data)

    def test_weather_form_rejects_unavailable_dates_or_reversed_times(self):
        base = dict(date=(jakarta_today()+timedelta(days=1)).isoformat(), start_time='08:00', end_time='18:00', max_rain='1', max_temperature='35')
        for changes in ({'date': '2000-01-01'}, {'date': (jakarta_today()+timedelta(days=7)).isoformat()},
                        {'start_time': '20:00', 'end_time': '10:00'}, {'max_rain': '-1'}, {'max_temperature': 'NaN'}):
            with self.subTest(changes=changes):
                form = PickupWeatherForm({**base, **changes})
                self.assertFalse(form.is_valid())
        self.assertTrue(PickupWeatherForm(base).is_valid())
