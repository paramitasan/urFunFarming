"""Fill the database with demo content so every page looks used.

Every demo account's username starts with demo_, and everything else this command makes
belongs to one of them, so --reset can remove it all without touching anyone else.
Each record is found by a stable key before it is made, so running it twice adds nothing new.
"""
from collections import Counter

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

        self.print_summary()

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
