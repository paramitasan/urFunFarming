import io
import shutil
import tempfile
from datetime import date, time

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from django.utils import timezone

from accounts.models import Profile
from journal.models import EntryPhoto, Garden, JournalEntry, PlantJournal, Planting

# Uploads made during tests go here, never into the real media/ folder
TEST_MEDIA = tempfile.mkdtemp()


def make_image(name='photo.png', image_format='PNG'):
    # A tiny real image file, made in memory
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), 'green').save(buffer, image_format)
    return SimpleUploadedFile(name, buffer.getvalue())


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class JournalTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)

    def setUp(self):
        self.grower = User.objects.create_user('ranu', password='Seedling-Tray-42')
        Profile.objects.create(user=self.grower, display_name='Ranu', is_grower=True)
        self.other_grower = User.objects.create_user('idris', password='Seedling-Tray-42')
        Profile.objects.create(user=self.other_grower, display_name='Idris', is_grower=True)
        self.buyer = User.objects.create_user('dewi', password='Seedling-Tray-42')
        Profile.objects.create(user=self.buyer, display_name='Dewi', is_buyer=True)

        self.garden = Garden.objects.create(name='Tebet Rooftop Garden', owner=self.grower)
        self.tomato = Planting.objects.create(name='Cherry Tomato', garden=self.garden)
        self.chili = Planting.objects.create(name="Bird's eye chili", garden=self.garden)
        self.journal = PlantJournal.objects.create(planting=self.tomato, is_public=False)

        self.first = JournalEntry.objects.create(
            planting=self.tomato, date=date(2026, 9, 12), time=time(7, 0),
            height_cm=8, stage='seedling', observation='First true leaves are out.',
        )
        self.second = JournalEntry.objects.create(
            planting=self.tomato, date=date(2026, 9, 22), time=time(17, 0),
            height_cm=34, stage='vegetative', observation='Moved into the rooftop garden.',
        )
        self.latest = JournalEntry.objects.create(
            planting=self.tomato, date=date(2026, 10, 24), time=time(7, 30),
            height_cm=92, stage='fruiting', observation='First fruits set on the lower truss.',
        )

    def entry_data(self, **changes):
        # A valid entry form, with any field swapped out for a test
        data = {
            'date': '2026-10-28',
            'time': '08:00',
            'height_cm': 95,
            'stage': 'fruiting',
            'health': 'healthy',
            'observation': 'More fruit this week.',
        }
        data.update(changes)
        return data


class ModelTest(JournalTestCase):
    def test_str(self):
        self.assertEqual(str(self.garden), 'Tebet Rooftop Garden')
        self.assertEqual(str(self.tomato), 'Cherry Tomato')
        self.assertEqual(str(self.journal), 'Journal for Cherry Tomato')
        self.assertEqual(str(self.latest), 'Cherry Tomato on 2026-10-24')

    def test_entries_are_newest_first(self):
        entries = list(self.tomato.journal_entries.all())
        self.assertEqual(entries, [self.latest, self.second, self.first])

    def test_journal_entries_plural_name(self):
        self.assertEqual(JournalEntry._meta.verbose_name_plural, 'journal entries')

    def test_photo_src_for_a_link(self):
        photo = EntryPhoto.objects.create(entry=self.latest, url='https://example.com/tomato.jpg')
        self.assertEqual(photo.src, 'https://example.com/tomato.jpg')
        self.assertEqual(str(photo), 'https://example.com/tomato.jpg')

    def test_photo_src_for_an_upload(self):
        photo = EntryPhoto.objects.create(entry=self.latest, image=make_image('leaf.png'))
        self.assertTrue(photo.src.startswith('/media/journal/leaf'))
        self.assertEqual(str(photo), photo.image.name)


class PlantDetailTest(JournalTestCase):
    def detail_url(self, planting):
        return reverse('journal:plant_detail', args=[planting.pk])

    def test_owner_sees_the_timeline_with_edit_links(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.tomato))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_owner'])
        self.assertContains(response, 'First fruits set on the lower truss.')
        self.assertContains(response, reverse('journal:edit_entry', args=[self.latest.pk]))
        self.assertContains(response, reverse('journal:create_plant_entry', args=[self.tomato.pk]))

    def test_private_journal_is_hidden_from_visitors(self):
        response = self.client.get(self.detail_url(self.tomato))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This journal is private.')
        self.assertNotContains(response, 'First fruits set on the lower truss.')

    def test_private_journal_is_hidden_from_other_growers(self):
        self.client.force_login(self.other_grower)
        response = self.client.get(self.detail_url(self.tomato))
        self.assertContains(response, 'This journal is private.')
        self.assertFalse(response.context['is_owner'])

    def test_public_journal_is_read_only_for_others(self):
        self.journal.is_public = True
        self.journal.save()
        self.client.force_login(self.buyer)
        response = self.client.get(self.detail_url(self.tomato))
        self.assertContains(response, 'First fruits set on the lower truss.')
        self.assertNotContains(response, reverse('journal:edit_entry', args=[self.latest.pk]))
        self.assertNotContains(response, reverse('journal:create_plant_entry', args=[self.tomato.pk]))

    def test_missing_plant_gives_404(self):
        response = self.client.get(reverse('journal:plant_detail', args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_height_change_between_entries(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.tomato))
        changes = [entry.height_change for entry in response.context['entries']]
        self.assertEqual(changes, [58, 26, None])
        self.assertContains(response, '+58 cm since last entry')
        self.assertContains(response, 'First entry')

    def test_started_on_and_days_growing(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.tomato))
        self.assertEqual(response.context['started_on'], date(2026, 9, 12))
        expected_days = (timezone.localdate() - date(2026, 9, 12)).days
        self.assertEqual(response.context['days_growing'], expected_days)

    def test_stage_steps(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.tomato))
        steps = response.context['stage_steps']
        self.assertEqual([step['status'] for step in steps], ['done', 'done', 'done', 'current', 'next'])
        # Flowering was skipped, so it is done but has no date
        self.assertEqual(steps[0]['date'], date(2026, 9, 12))
        self.assertIsNone(steps[2]['date'])
        self.assertEqual(steps[3]['date'], date(2026, 10, 24))

    def test_plant_without_entries_shows_empty_state(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.chili))
        self.assertContains(response, 'No entries yet')
        self.assertIsNone(response.context['days_growing'])
        self.assertEqual({step['status'] for step in response.context['stage_steps']}, {'next'})

    def test_back_link_goes_to_journal_by_default(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.tomato))
        self.assertContains(response, 'Back to journal')
        self.assertNotContains(response, 'Back to Tebet Rooftop Garden')

    def test_back_link_goes_to_garden_when_opened_from_it(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.tomato) + '?from=garden')
        self.assertContains(response, 'Back to Tebet Rooftop Garden')
        self.assertNotContains(response, 'Back to journal')

    def test_photos_show_on_the_card(self):
        EntryPhoto.objects.create(entry=self.latest, url='https://example.com/tomato.jpg')
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url(self.tomato))
        self.assertContains(response, 'src="https://example.com/tomato.jpg"')
