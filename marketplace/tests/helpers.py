from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from accounts.models import Profile
from marketplace.dates import jakarta_today
from marketplace.models import HarvestListing


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MarketplaceCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('grower', password='garden-test-password')
        cls.other = User.objects.create_user('other_grower', password='garden-test-password')
        cls.buyer = User.objects.create_user('buyer', password='garden-test-password')
        cls.no_profile = User.objects.create_user('no_profile', password='garden-test-password')
        cls.profile = Profile.objects.create(
            user=cls.owner, display_name='Ayu Grower', is_grower=True, is_buyer=True,
            area='Beji', city='Depok', phone='+628123456789', contact_email='private-contact@example.com',
            bio='I grow herbs on my balcony.',
        )
        Profile.objects.create(user=cls.other, display_name='Other Grower', is_grower=True)
        Profile.objects.create(user=cls.buyer, display_name='Buyer', is_buyer=True)
        cls.listing = cls.make_listing()

    @classmethod
    def make_listing(cls, **changes):
        fields = dict(
            owner=cls.owner, title='Fresh basil', description='Freshly harvested basil for local collection.',
            category='herbs', quantity=Decimal('6'), unit='bunch', price=Decimal('12000'), price_quantity=Decimal('2'),
            area='Beji', city='Depok', available_from=jakarta_today(), available_until=jakarta_today()+timedelta(days=5),
        )
        fields.update(changes)
        return HarvestListing.objects.create(**fields)

    def data(self, **changes):
        fields = dict(
            title='Fresh tomatoes', description='Rooftop tomatoes. Contact me to collect.', category='fruits',
            quantity='1500', unit='g', price='15000', price_quantity='500', area='Kukusan', city='Depok',
            image_url='', available_from=jakarta_today().isoformat(),
            available_until=(jakarta_today()+timedelta(days=3)).isoformat(), is_available=True,
        )
        fields.update(changes)
        return fields
