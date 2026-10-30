from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.locations import find_village
from accounts.models import Profile
from care.models import CareTask
from forum.models import Forum, Reply
from gardens.models import Garden, Planting
from journal.models import JournalEntry
from marketplace.models import HarvestListing

# The test runner turns DEBUG off, which the command refuses without --force, so turn it back on.
# A fast hasher keeps the eight demo passwords from slowing every test down.
FAST_DEMO = override_settings(
    DEBUG=True,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    DEMO_PASSWORD='test-demo-password',
)


def seed(*args):
    out = StringIO()
    call_command('seed_demo', *args, stdout=out)
    return out.getvalue()


def demo_counts():
    return {
        'users': User.objects.filter(username__startswith='demo_').count(),
        'profiles': Profile.objects.filter(user__username__startswith='demo_').count(),
        'gardens': Garden.objects.filter(owner__username__startswith='demo_').count(),
        'plantings': Planting.objects.filter(garden__owner__username__startswith='demo_').count(),
        'journal entries': JournalEntry.objects.filter(planting__garden__owner__username__startswith='demo_').count(),
        'care tasks': CareTask.objects.filter(owner__username__startswith='demo_').count(),
        'listings': HarvestListing.objects.filter(owner__username__startswith='demo_').count(),
        'questions': Forum.objects.filter(author__username__startswith='demo_').count(),
        'answers': Reply.objects.filter(author__username__startswith='demo_').count(),
    }


@FAST_DEMO
class SeedDemoContentTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.output = seed()

    def test_creates_the_expected_counts(self):
        counts = demo_counts()
        self.assertEqual(counts['users'], 8)
        self.assertEqual(counts['profiles'], 8)
        self.assertEqual(counts['gardens'], 16)
        self.assertEqual(counts['plantings'], 50)
        self.assertEqual(counts['care tasks'], 30)
        self.assertEqual(counts['listings'], 54)
        self.assertEqual(counts['questions'], 15)
        self.assertEqual(counts['answers'], 47)
        self.assertGreaterEqual(counts['journal entries'], 3 * 43)

    def test_prints_a_summary(self):
        self.assertIn('gardens: 16 created, 0 already there', self.output)
        self.assertIn('market listings: 54 created', self.output)
        self.assertNotIn('Skipped', self.output)

    def test_users_have_roles_profiles_and_the_shared_password(self):
        profiles = Profile.objects.filter(user__username__startswith='demo_')
        self.assertEqual(profiles.filter(is_grower=True, is_buyer=False).count(), 4)
        self.assertEqual(profiles.filter(is_grower=False, is_buyer=True).count(), 2)
        self.assertEqual(profiles.filter(is_grower=True, is_buyer=True).count(), 2)
        for profile in profiles:
            with self.subTest(user=profile.user.username):
                self.assertTrue(profile.user.check_password('test-demo-password'))
                self.assertTrue(profile.display_name and profile.bio)
                place = find_village(profile.adm4_code)
                self.assertIsNotNone(place)
                self.assertEqual((profile.area, profile.city), (place['district'], place['city']))

    def test_gardens_and_plantings(self):
        today = timezone.localdate()
        for grower in User.objects.filter(username__startswith='demo_', profile__is_grower=True):
            gardens = grower.gardens.all()
            with self.subTest(grower=grower.username):
                self.assertIn(gardens.count(), [2, 3])
                self.assertEqual(set(gardens.values_list('is_public', flat=True)), {True, False})
            for garden in gardens:
                self.assertIn(garden.plantings.count(), range(2, 6))
                for planting in garden.plantings.all():
                    self.assertTrue(today - timedelta(days=60) <= planting.planting_date < today)
        self.assertFalse(Garden.objects.filter(owner__profile__is_grower=False).exists())

    def test_journal_entries_run_in_order_from_planting_day_to_today(self):
        today = timezone.localdate()
        plantings = Planting.objects.filter(garden__owner__username__startswith='demo_')
        empty = [p for p in plantings if not p.journal_entries.exists()]
        self.assertTrue(empty, 'some plantings should show the empty journal')
        for planting in plantings.exclude(pk__in=[p.pk for p in empty]):
            dates = list(planting.journal_entries.order_by('date', 'time').values_list('date', flat=True))
            with self.subTest(planting=planting.name):
                self.assertIn(len(dates), range(3, 11))
                self.assertEqual(dates[0], planting.planting_date)
                self.assertEqual(dates[-1], today)
                self.assertEqual(dates, sorted(set(dates)))
        stages = set(JournalEntry.objects.values_list('stage', flat=True))
        self.assertEqual(stages, {'seedling', 'vegetative', 'flowering', 'fruiting', 'harvested'})

    def test_care_tasks_mix_statuses_on_own_plantings(self):
        for grower in User.objects.filter(username__startswith='demo_', profile__is_grower=True):
            tasks = CareTask.objects.filter(owner=grower)
            with self.subTest(grower=grower.username):
                self.assertEqual(set(tasks.values_list('status', flat=True)), {'todo', 'in_progress', 'completed'})
                self.assertFalse(tasks.exclude(planting__garden__owner=grower).exists())

    def test_listings(self):
        listings = HarvestListing.objects.filter(owner__username__startswith='demo_')
        self.assertGreaterEqual(listings.count(), 50)
        self.assertTrue(listings.filter(price=0).exists())
        self.assertTrue(listings.filter(price__gt=0).exists())
        self.assertFalse(listings.filter(is_demo=False).exists())
        self.assertFalse(listings.filter(owner__profile__is_grower=False).exists())
        self.assertGreaterEqual(HarvestListing.objects.available_now().count(), 30)

    def test_forum_answers_come_from_other_demo_users(self):
        questions = Forum.objects.filter(author__username__startswith='demo_')
        self.assertEqual(questions.count(), 15)
        self.assertGreaterEqual(questions.values('topic').distinct().count(), 5)
        for question in questions:
            with self.subTest(question=question.title):
                self.assertLessEqual(question.replies.count(), 6)
                self.assertFalse(question.replies.filter(author=question.author).exists())
                self.assertFalse(question.is_edited)
        self.assertTrue(questions.filter(replies__isnull=True).exists())

    def test_leaves_photos_empty(self):
        self.assertFalse(Garden.objects.exclude(photo='', photo_url='').exists())
        self.assertFalse(Planting.objects.exclude(photo='', photo_url='').exists())
        self.assertFalse(HarvestListing.objects.exclude(image_url='').exists())
        self.assertFalse(apps.get_model('journal', 'EntryPhoto').objects.exists())


@FAST_DEMO
class SeedDemoPrivacyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()
        cls.owner = User.objects.get(username='demo_ayu')
        cls.other = User.objects.get(username='demo_sekar')
        cls.private = cls.owner.gardens.filter(is_public=False).first()
        cls.planting = cls.private.plantings.first()

    def test_private_garden_is_hidden_from_other_users(self):
        self.client.force_login(self.other)
        explore = self.client.get(reverse('gardens:explore'))
        self.assertNotContains(explore, self.private.name)
        self.assertEqual(self.client.get(reverse('gardens:public_detail', args=[self.private.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('gardens:detail', args=[self.private.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('journal:plant_detail', args=[self.planting.pk])).status_code, 403)

    def test_private_garden_is_hidden_from_visitors(self):
        self.assertNotContains(self.client.get(reverse('gardens:explore')), self.private.name)
        self.assertEqual(self.client.get(reverse('gardens:public_detail', args=[self.private.pk])).status_code, 404)

    def test_owner_still_sees_the_private_garden(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('gardens:detail', args=[self.private.pk]))
        self.assertContains(response, self.private.name)


@FAST_DEMO
class SeedDemoBehaviourTest(TestCase):
    def test_running_twice_adds_nothing(self):
        seed()
        before = demo_counts()
        output = seed()
        self.assertEqual(demo_counts(), before)
        self.assertIn('users: 0 created, 8 already there', output)
        self.assertIn('journal entries: 0 created', output)

    def test_same_data_on_every_run(self):
        def snapshot():
            return (
                list(Planting.objects.order_by('name').values_list('name', 'planting_date')),
                list(HarvestListing.objects.order_by('pk').values_list('pk', 'title', 'price', 'quantity')),
                list(JournalEntry.objects.order_by('planting__name', 'date').values_list('observation', 'height_cm')),
            )
        seed()
        first = snapshot()
        seed('--reset')
        self.assertEqual(snapshot(), first)

    def test_reset_only_removes_demo_data(self):
        real = User.objects.create_user('sari', password='real-password-1')
        Profile.objects.create(user=real, display_name='Sari', is_grower=True)
        garden = Garden.objects.create(owner=real, name='Real Garden', location='Depok', growing_method='Pots')
        Planting.objects.create(garden=garden, crop='Kangkung', planting_date=timezone.localdate())
        Forum.objects.create(author=real, title='A real question', description='Real')
        # On SQLite startswith ignores case, so this account must survive too
        lookalike = User.objects.create_user('DEMO_lookalike', password='real-password-2')

        seed()
        HarvestListing.objects.filter(owner__username='demo_ayu').delete()
        output = seed('--reset')

        self.assertIn('Reset: removed 8 demo_ accounts', output)
        self.assertEqual(User.objects.filter(pk__in=[real.pk, lookalike.pk]).count(), 2)
        self.assertTrue(Garden.objects.filter(pk=garden.pk, plantings__crop='Kangkung').exists())
        self.assertTrue(Forum.objects.filter(author=real).exists())
        self.assertTrue(real.check_password('real-password-1'))
        self.assertEqual(demo_counts()['listings'], 54)

    def test_refuses_to_run_when_debug_is_off(self):
        with override_settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, '--force'):
                seed()
            self.assertFalse(User.objects.filter(username__startswith='demo_').exists())
            seed('--force')
        self.assertEqual(demo_counts()['users'], 8)

    def test_leaves_a_real_account_with_a_demo_username_alone(self):
        real = User.objects.create_user('demo_ayu', email='ayu@ui.ac.id', password='real-password-1')
        with self.assertRaises(CommandError):
            seed()
        real.refresh_from_db()
        self.assertTrue(real.check_password('real-password-1'))
        self.assertEqual(User.objects.count(), 1)

    def test_skips_a_part_whose_model_does_not_exist(self):
        get_model = apps.get_model

        def without_journal_entries(app_label, model_name):
            if (app_label, model_name) == ('journal', 'JournalEntry'):
                raise LookupError(model_name)
            return get_model(app_label, model_name)

        with patch('main.management.commands.seed_demo.apps.get_model', side_effect=without_journal_entries):
            output = seed()
        self.assertIn('Skipped:', output)
        self.assertIn('journal.JournalEntry does not exist yet', output)
        self.assertFalse(JournalEntry.objects.exists())
        self.assertEqual(demo_counts()['listings'], 54)
