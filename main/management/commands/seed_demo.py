"""Fill the database with demo content so every page looks used.

Every demo account's username starts with demo_, and everything else this command makes
belongs to one of them, so --reset can remove it all without touching anyone else.
Each record is found by a stable key before it is made, so running it twice adds nothing new.
"""
import random
from collections import Counter
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.locations import find_village
from accounts.models import Profile

PREFIX = 'demo_'
SEED = 2026

# username, display name, grower, buyer, BMKG village code (adm4), bio
USERS = [
    ('demo_ayu', 'Ayu Lestari', True, False, '31.74.01.1001',
     'Rooftop grower in Tebet. Pak choy and selada in grow bags, plus one stubborn tomat ceri.'),
    ('demo_bima', 'Bima Prasetyo', True, False, '32.76.06.1002',
     'Student in Kukusan growing kangkung and cabai rawit on a small NFT rack behind the kos.'),
    ('demo_rina', 'Rina Wulandari', True, False, '31.75.02.1005',
     'Balcony herbs in Rawamangun: basil, mint and serai. Happy to swap cuttings with neighbours.'),
    ('demo_dimas', 'Dimas Saputra', True, False, '32.76.01.1008',
     'Backyard beds and a wick hydroponic shelf in Pancoran Mas. Learning tomat ceri the hard way.'),
    ('demo_nadia', 'Nadia Putri', True, True, '32.76.06.1001',
     'Terrace greens in Beji. I sell my extra selada and buy the herbs I cannot keep alive.'),
    ('demo_yoga', 'Yoga Pratama', True, True, '31.74.09.1004',
     'Community garden volunteer near Lenteng Agung station. Mostly cabai and kangkung.'),
    ('demo_sekar', 'Sekar Ayuningtyas', False, True, '31.74.01.1003',
     'Home cook in Menteng Dalam who likes knowing who grew the vegetables.'),
    ('demo_fajar', 'Fajar Nugroho', False, True, '32.76.06.1005',
     'Runs a small warung near campus in Pondok Cina and buys fresh herbs and greens every week.'),
]

# owner: [(garden name, location, growing method, public, public summary, private notes,
#          [(planting name, crop, optional growing method), ...])]
# Planting names are unique across the demo, so later parts can refer to a planting by name.
GARDENS = {
    'demo_ayu': [
        ('Rooftop Grow Bags', 'Tebet, Jakarta Selatan', 'Grow bags', True,
         'Twelve grow bags on the roof of our rumah susun, full sun from 9 to 3.',
         'Roof door key is with Pak RT. Water is off from 10:00 to 14:00.',
         [('Rooftop pak choy', 'Pak choy'), ('Rooftop selada keriting', 'Selada'),
          ('Tomat ceri by the water tank', 'Tomat ceri'), ('Rooftop cabai rawit', 'Cabai rawit')]),
        ('Kitchen Window Herbs', 'Tebet, Jakarta Selatan', 'Pots', False,
         'Two pots on the kitchen window ledge.',
         'Window only gets sun until 11. Turn the pots every few days.',
         [('Kitchen basil', 'Basil'), ('Kitchen mint', 'Mint')]),
        ('Stairwell Seed Trays', 'Tebet, Jakarta Selatan', 'Recycled trays', True,
         'Old egg trays and takeaway boxes on the stairwell railing, shared with the neighbours.',
         'Ask Bu Ani before moving her trays.',
         [('Stairwell kangkung', 'Kangkung'), ('Stairwell pak choy', 'Pak choy'), ('Stairwell selada', 'Selada')]),
    ],
    'demo_bima': [
        ('Kos NFT Rack', 'Beji, Depok', 'NFT hydroponics', True,
         'A four-pipe NFT rack behind the kos, built from PVC and a fish tank pump.',
         'Pump is on the timer by the laundry tap. AB mix is under the sink.',
         [('NFT kangkung', 'Kangkung'), ('NFT pak choy', 'Pak choy'), ('NFT selada', 'Selada'),
          ('NFT basil', 'Basil'), ('Mint cuttings in a jar', 'Mint', 'Water propagation')]),
        ('Cabai Corner', 'Beji, Depok', 'Polybags', False,
         'Polybags along the back fence.',
         'Landlord asked to keep the path clear. Neem oil is in the blue bottle.',
         [('Cabai rawit hijau', 'Cabai rawit'), ('Cabai rawit merah', 'Cabai rawit'),
          ('Polybag tomat ceri', 'Tomat ceri')]),
    ],
    'demo_rina': [
        ('Rawamangun Balcony Herbs', 'Pulogadung, Jakarta Timur', 'Containers', True,
         'A sunny third-floor balcony packed with herbs for cooking and tea.',
         'Neighbour below complained about drips, so water before 7.',
         [('Balcony basil', 'Basil'), ('Thai basil (kemangi)', 'Basil'), ('Balcony mint', 'Mint'),
          ('Balcony selada', 'Selada')]),
        ('Laundry Line Planters', 'Pulogadung, Jakarta Timur', 'Hanging planters', False,
         'Hanging planters on the old laundry line.',
         'Hooks on the left side are loose. Do not hang anything heavier than 3 kg.',
         [('Hanging kangkung', 'Kangkung'), ('Hanging mint', 'Mint')]),
        ('Front Gate Pots', 'Pulogadung, Jakarta Timur', 'Pots', True,
         'Big pots by the front gate that everyone on the gang walks past.',
         'Kids pick the tomatoes, which is fine. Keep the cabai out of reach.',
         [('Gate cabai rawit', 'Cabai rawit'), ('Gate tomat ceri', 'Tomat ceri'), ('Gate basil', 'Basil')]),
    ],
    'demo_dimas': [
        ('Backyard Raised Beds', 'Pancoran Mas, Depok', 'Raised beds', True,
         'Three raised beds made from old pallets, filled with compost from the RW bank sampah.',
         'Bed 3 drains badly after heavy rain. Compost bin is behind the shed.',
         [('Raised bed tomat ceri', 'Tomat ceri'), ('Raised bed cabai rawit', 'Cabai rawit'),
          ('Raised bed pak choy', 'Pak choy'), ('Raised bed kangkung', 'Kangkung'), ('Raised bed selada', 'Selada')]),
        ('Wick Hydroponic Shelf', 'Pancoran Mas, Depok', 'Wick hydroponics', True,
         'A three-level shelf of wick pots under the carport roof.',
         'Top up the reservoirs every Monday and Thursday.',
         [('Wick selada', 'Selada'), ('Wick pak choy', 'Pak choy'), ('Wick basil', 'Basil')]),
        ('Seedling Nursery', 'Pancoran Mas, Depok', 'Seedling trays', False,
         'Seedling trays on a shelf by the kitchen door.',
         'Keep the shade net on until the seedlings have four leaves.',
         [('Nursery tomat ceri', 'Tomat ceri'), ('Nursery cabai rawit', 'Cabai rawit')]),
    ],
    'demo_nadia': [
        ('Beji Terrace Greens', 'Beji, Depok', 'Containers', True,
         'Long planter boxes along the terrace railing, mostly leafy greens.',
         'The tap on the terrace leaks, close it tight.',
         [('Terrace selada', 'Selada'), ('Terrace pak choy', 'Pak choy'), ('Terrace kangkung', 'Kangkung')]),
        ('Bedroom Window Sill', 'Beji, Depok', 'Pots', False,
         'Two small pots on the bedroom window sill.',
         'Only morning sun here. Mint likes it, basil not so much.',
         [('Window mint', 'Mint'), ('Window basil', 'Basil')]),
    ],
    'demo_yoga': [
        ('Lenteng Agung Community Plot', 'Jagakarsa, Jakarta Selatan', 'In-ground beds', True,
         'A shared plot near Lenteng Agung station, tended by volunteers every Saturday morning.',
         'Tool shed code is 2306. Log what you take in the book.',
         [('Community cabai rawit', 'Cabai rawit'), ('Community kangkung', 'Kangkung'),
          ('Community tomat ceri', 'Tomat ceri'), ('Community pak choy', 'Pak choy')]),
        ('Station Fence Planters', 'Jagakarsa, Jakarta Selatan', 'Vertical planters', True,
         'Vertical planters made from paint buckets, hung on the fence by the station path.',
         'Two planters were knocked down last month. Check the wire ties.',
         [('Vertical selada', 'Selada'), ('Vertical mint', 'Mint'), ('Vertical basil', 'Basil')]),
        ('Home Dutch Bucket', 'Jagakarsa, Jakarta Selatan', 'Dutch bucket hydroponics', False,
         'Two dutch buckets in the side yard.',
         'Pump fuse blew once. Spare fuse is taped under the reservoir lid.',
         [('Dutch bucket tomat ceri', 'Tomat ceri'), ('Dutch bucket cabai rawit', 'Cabai rawit')]),
    ],
}
SLOW_CROPS = {'Tomat ceri', 'Cabai rawit'}


class Command(BaseCommand):
    help = 'Create demo users, gardens, journals, care tasks, listings and forum posts. Safe to run more than once.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete every demo_ account and what it owns, then seed again.')
        parser.add_argument('--force', action='store_true', help='Allow running while DEBUG is off, e.g. on PWS.')

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError('DEBUG is off, so this looks like a live site. Add --force if you really want demo data here.')

        self.today = timezone.localdate()
        self.created = Counter()
        self.existing = Counter()
        self.skipped = []
        self.removed = 0

        # All or nothing: if one part fails, the database is left as it was
        with transaction.atomic():
            if options['reset']:
                self.reset()
            self.seed_users()
            self.seed_gardens()

        self.print_summary()

    def rng(self, *key):
        # Each record gets its own generator from the fixed seed, so its values are the same
        # on every run and never depend on what else already exists
        return random.Random(':'.join(str(part) for part in (SEED, *key)))

    def model(self, app_label, model_name, part):
        # A missing app or model skips its part, so the command still runs while a module is unfinished
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            self.skipped.append(f'{part} ({app_label}.{model_name} does not exist yet)')
            return None

    def tally(self, label, created):
        (self.created if created else self.existing)[label] += 1

    def reset(self):
        # On SQLite startswith ignores case, so check the exact prefix again in Python.
        # Gardens, journals, tasks, listings and forum posts all belong to a user,
        # so deleting the demo users removes everything they own and nothing else.
        demo_ids = [
            user.pk for user in User.objects.filter(username__startswith=PREFIX)
            if user.username.startswith(PREFIX)
        ]
        self.removed = len(demo_ids)
        User.objects.filter(pk__in=demo_ids).delete()

    def seed_users(self):
        password = settings.DEMO_PASSWORD
        self.users = {}
        for username, display_name, is_grower, is_buyer, code, bio in USERS:
            email = f'{username}@example.invalid'
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            if not created and user.email != email:
                raise CommandError(f'{username} already belongs to a real account, so no demo data was changed.')
            # Only rehash when the password setting changed, so reruns stay quick
            if created or not user.check_password(password):
                user.set_password(password)
                user.save()
            self.tally('users', created)

            # Area and city come from the village code, the same way the profile form fills them
            place = find_village(code)
            _, created = Profile.objects.get_or_create(user=user, defaults={
                'display_name': display_name, 'is_grower': is_grower, 'is_buyer': is_buyer, 'bio': bio,
                'adm4_code': code, 'area': place['district'], 'city': place['city'], 'contact_email': email,
            })
            self.tally('profiles', created)
            self.users[username] = user

        self.growers = [self.users[row[0]] for row in USERS if row[2]]

    def seed_gardens(self):
        self.plantings = {}
        Garden = self.model('gardens', 'Garden', 'gardens and plantings')
        if not Garden:
            return
        Planting = self.model('gardens', 'Planting', 'plantings')

        for username, gardens in GARDENS.items():
            for name, location, method, is_public, summary, notes, plants in gardens:
                garden, created = Garden.objects.get_or_create(owner=self.users[username], name=name, defaults={
                    'location': location, 'growing_method': method, 'is_public': is_public,
                    'public_summary': summary, 'private_notes': notes,
                })
                self.tally('gardens', created)
                if not Planting:
                    continue

                for plant_name, crop, *plant_method in plants:
                    # Planted some time in the past two months; fruit crops grow slowly, so they went in earlier
                    earliest = 25 if crop in SLOW_CROPS else 2
                    planted = self.today - timedelta(days=self.rng('planting', plant_name).randint(earliest, 60))
                    planting, created = Planting.objects.get_or_create(garden=garden, name=plant_name, defaults={
                        'crop': crop, 'planting_date': planted, 'growing_method': plant_method[0] if plant_method else '',
                    })
                    self.tally('plantings', created)
                    self.plantings[plant_name] = planting

    def print_summary(self):
        if self.removed:
            self.stdout.write(f'Reset: removed {self.removed} demo_ accounts and everything they owned.')
        for label in [*self.created, *(k for k in self.existing if k not in self.created)]:
            self.stdout.write(f'  {label}: {self.created[label]} created, {self.existing[label]} already there')
        if self.skipped:
            self.stdout.write(self.style.WARNING('Skipped:'))
            for part in self.skipped:
                self.stdout.write(f'  {part}')
        names = ', '.join(row[0] for row in USERS)
        self.stdout.write(self.style.SUCCESS(f'Demo data ready. Log in as {names} with the DEMO_PASSWORD setting.'))
