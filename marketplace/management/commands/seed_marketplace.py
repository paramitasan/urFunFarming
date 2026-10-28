from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Profile
from marketplace.dates import jakarta_today
from marketplace.models import HarvestListing


class Command(BaseCommand):
    help = 'Create or refresh 50 clearly labelled demo harvests from 10 fictional growers, without changing real accounts or listings.'

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        growers = [('Ayu', 'Beji', 'Depok'), ('Bima', 'Kukusan', 'Depok'), ('Sari', 'Margonda', 'Depok'),
                   ('Dimas', 'Tebet', 'Jakarta'), ('Nadia', 'Pancoran Mas', 'Depok'), ('Raka', 'Menteng', 'Jakarta'),
                   ('Sekar', 'Kemang', 'Jakarta'), ('Bayu', 'Cikini', 'Jakarta'), ('Rina', 'Rawamangun', 'Jakarta'), ('Yoga', 'Bintaro', 'Tangerang')]
        crops = [
            ('Butterhead lettuce', 'vegetables', 'head', '4', '9000', '2'),
            ('Cherry tomatoes', 'fruits', 'g', '1500', '15000', '500'),
            ('Thai basil', 'herbs', 'bunch', '6', '0', '1'),
            ('Garden carrots', 'vegetables', 'kg', '5', '12000', '1'),
            ('Kangkung', 'vegetables', 'bunch', '6', '8000', '2'),
            ('Red chilies', 'vegetables', 'g', '500', '12000', '100'),
            ('Sweet mint', 'herbs', 'bunch', '3', '0', '1'),
            ('Crisp cucumbers', 'vegetables', 'kg', '3', '10000', '1'),
            ('Fresh pak choi', 'vegetables', 'bunch', '8', '8000', '1'),
            ('Passion fruit', 'fruits', 'piece', '10', '5000', '2'),
        ]
        for i, (name, area, city) in enumerate(growers):
            username = f'demo_grower_{i+1:02d}'
            email = username + '@example.invalid'
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            if not created and (user.email != email or user.has_usable_password()):
                raise CommandError(f'{username} already belongs to a different account. No demo data was changed.')
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password'])
            Profile.objects.update_or_create(user=user, defaults={
                'display_name': name, 'is_grower': True, 'is_buyer': True, 'area': area, 'city': city,
                'bio': 'Fictional grower profile for the university project demo.', 'phone': '', 'contact_email': email,
            })
            for j in range(5):
                title, category, unit, quantity, price, price_quantity = crops[(i + j) % len(crops)]
                pk = uuid5(NAMESPACE_URL, f'urfunfarming/marketplace/demo/{i}/{j}')
                existing = HarvestListing.objects.filter(pk=pk).first()
                if existing and (not existing.is_demo or existing.owner_id != user.pk):
                    raise CommandError('A demo identifier belongs to a non-demo offer. No records were changed.')
                HarvestListing.objects.update_or_create(pk=pk, defaults={
                    'owner': user, 'title': title, 'category': category, 'unit': unit,
                    'quantity': Decimal(quantity), 'price': Decimal(price), 'price_quantity': Decimal(price_quantity),
                    'description': f'Demonstration listing: {title.lower()} from a fictional urban garden. Contact the grower to discuss local collection. This is sample data, not a real offer.',
                    'area': area, 'city': city, 'image_url': '', 'is_available': True, 'is_demo': True,
                    'available_from': jakarta_today(), 'available_until': jakarta_today() + timedelta(days=7 + j),
                })
        self.stdout.write(self.style.SUCCESS('50 demo harvest listings are ready. Demo accounts cannot log in; real records were preserved.'))
