import io
import shutil
import tempfile
from datetime import date, time

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

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
