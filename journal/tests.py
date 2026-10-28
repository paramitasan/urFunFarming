import io
import shutil
import tempfile
from datetime import date, time
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from accounts.models import Profile
from journal.models import EntryPhoto, Garden, JournalEntry, PlantJournal, Planting
from journal.forms import PHOTO_ERROR, JournalEntryForm, NewEntryForm

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


class EntryFormTest(JournalTestCase):
    def make_form(self, files=None, **changes):
        data = {**self.entry_data(**changes), 'planting': self.tomato.pk, 'visibility': 'private'}
        return NewEntryForm(self.grower, data, MultiValueDict({'photos': files or []}))

    def test_plant_choices_are_only_your_own(self):
        mine = NewEntryForm(self.grower).fields['planting'].queryset
        self.assertEqual(set(mine), {self.tomato, self.chili})
        theirs = NewEntryForm(self.other_grower).fields['planting'].queryset
        self.assertFalse(theirs.exists())

    def test_someone_elses_plant_is_rejected(self):
        data = {**self.entry_data(), 'planting': self.tomato.pk, 'visibility': 'private'}
        form = NewEntryForm(self.other_grower, data)
        self.assertFalse(form.is_valid())
        self.assertIn('planting', form.errors)

    def test_required_fields_use_the_design_messages(self):
        form = NewEntryForm(self.grower, {'visibility': 'private'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['planting'], ['Please choose a plant.'])
        self.assertEqual(form.errors['date'], ['Please pick a date.'])
        self.assertEqual(form.errors['time'], ['Please enter the time.'])
        self.assertEqual(form.errors['height_cm'], ['Please enter the height in cm.'])
        self.assertEqual(form.errors['observation'], ['Please write what you noticed.'])

    def test_html_is_removed_from_the_observation(self):
        form = self.make_form(observation='Hello <script>alert(1)</script> there')
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['observation'], 'Hello alert(1) there')

    def test_observation_with_only_tags_counts_as_empty(self):
        form = self.make_form(observation='<b></b>')
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['observation'], ['Please write what you noticed.'])

    def test_visibility_starts_private_and_is_only_on_the_new_form(self):
        self.assertEqual(NewEntryForm(self.grower).fields['visibility'].initial, 'private')
        self.assertNotIn('visibility', JournalEntryForm(self.grower).fields)

    def test_photo_links_are_collected_in_order(self):
        form = self.make_form(photo_1='https://example.com/a.jpg', photo_3='example.com/b.jpg')
        self.assertTrue(form.is_valid())
        self.assertEqual(form.photo_urls(), ['https://example.com/a.jpg', 'https://example.com/b.jpg'])

    def test_unsafe_photo_link_is_rejected(self):
        form = self.make_form(photo_1='javascript:alert(1)')
        self.assertFalse(form.is_valid())
        self.assertIn('photo_1', form.errors)

    def test_jpg_png_and_webp_uploads_are_accepted(self):
        files = [make_image('a.jpg', 'JPEG'), make_image('b.png', 'PNG'), make_image('c.webp', 'WEBP')]
        form = self.make_form(files=files)
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.cleaned_data['photos']), 3)

    def test_gif_is_rejected_even_when_renamed(self):
        for name in ('plant.gif', 'plant.png'):
            form = self.make_form(files=[make_image(name, 'GIF')])
            self.assertFalse(form.is_valid())
            self.assertEqual(form.errors['photos'], [PHOTO_ERROR])

    def test_file_that_is_not_an_image_is_rejected(self):
        form = self.make_form(files=[SimpleUploadedFile('plant.jpg', b'not an image')])
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['photos'], [PHOTO_ERROR])

    def test_photo_over_the_size_limit_is_rejected(self):
        # Lower the limit for this test instead of building a real 5 MB file
        with mock.patch('journal.forms.MAX_PHOTO_SIZE', 10):
            form = self.make_form(files=[make_image('big.png')])
            self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['photos'], [PHOTO_ERROR])

    def test_five_photos_is_the_limit(self):
        links = {'photo_1': 'https://example.com/1.jpg', 'photo_2': 'https://example.com/2.jpg'}
        five = self.make_form(files=[make_image(f'{i}.png') for i in range(3)], **links)
        self.assertTrue(five.is_valid())
        six = self.make_form(files=[make_image(f'{i}.png') for i in range(4)], **links)
        self.assertFalse(six.is_valid())
        self.assertEqual(six.errors['photos'], ['You can add up to 5 photos to one entry.'])

    def test_kept_photos_count_towards_the_limit(self):
        form = self.make_form(files=[make_image('a.png'), make_image('b.png')])
        form.kept_photos = 4
        self.assertFalse(form.is_valid())
        self.assertIn('photos', form.errors)


class CreateEntryTest(JournalTestCase):
    new_url = reverse('journal:create_entry')

    def plant_url(self, planting):
        return reverse('journal:create_plant_entry', args=[planting.pk])

    def toasts(self, response):
        return [str(message) for message in response.context['messages']]

    def test_visitor_is_sent_to_login(self):
        response = self.client.get(self.new_url)
        self.assertRedirects(response, '/login?next=/journal/new/', fetch_redirect_response=False)

    def test_buyer_sees_the_growers_only_page(self):
        self.client.force_login(self.buyer)
        response = self.client.get(self.new_url)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'journal/grower_required.html')

    def test_new_entry_page_has_plant_and_visibility(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.new_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('planting', response.context['form'].fields)
        self.assertIn('visibility', response.context['form'].fields)
        self.assertContains(response, 'Back to journal')

    def test_saving_an_entry_with_photos_and_visibility(self):
        self.client.force_login(self.grower)
        data = self.entry_data(
            planting=self.chili.pk, visibility='public',
            photos=[make_image('leaf.png')], photo_1='https://example.com/chili.jpg',
        )
        response = self.client.post(self.new_url, data, follow=True)
        self.assertRedirects(response, reverse('journal:plant_detail', args=[self.chili.pk]))
        self.assertIn('Entry saved', self.toasts(response))

        entry = self.chili.journal_entries.get()
        self.assertEqual(entry.height_cm, 95)
        self.assertEqual(entry.photos.count(), 2)
        self.assertEqual(entry.photos.filter(url='https://example.com/chili.jpg').count(), 1)
        # The chili had no journal yet, so saving made one with the chosen visibility
        self.assertTrue(PlantJournal.objects.get(planting=self.chili).is_public)

    def test_private_choice_makes_the_journal_private(self):
        self.journal.is_public = True
        self.journal.save()
        self.client.force_login(self.grower)
        self.client.post(self.new_url, self.entry_data(planting=self.tomato.pk, visibility='private'))
        self.journal.refresh_from_db()
        self.assertFalse(self.journal.is_public)

    def test_plant_version_starts_on_the_current_stage(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.plant_url(self.tomato))
        form = response.context['form']
        self.assertNotIn('planting', form.fields)
        self.assertNotIn('visibility', form.fields)
        self.assertEqual(form.initial['stage'], 'fruiting')
        self.assertEqual(response.context['latest'], self.latest)
        self.assertContains(response, 'New Entry for Cherry Tomato')
        self.assertContains(response, 'Last time: 92 cm')

    def test_plant_version_saves_without_changing_visibility(self):
        self.journal.is_public = True
        self.journal.save()
        self.client.force_login(self.grower)
        response = self.client.post(self.plant_url(self.tomato), self.entry_data())
        self.assertRedirects(response, reverse('journal:plant_detail', args=[self.tomato.pk]))
        self.assertEqual(self.tomato.journal_entries.count(), 4)
        self.journal.refresh_from_db()
        self.assertTrue(self.journal.is_public)

    def test_plant_without_entries_says_so(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.plant_url(self.chili))
        self.assertIsNone(response.context['latest'])
        self.assertContains(response, 'No entries yet')

    def test_someone_elses_plant_gives_403(self):
        self.client.force_login(self.other_grower)
        response = self.client.post(self.plant_url(self.tomato), self.entry_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.tomato.journal_entries.count(), 3)

    def test_missing_plant_gives_404(self):
        self.client.force_login(self.grower)
        response = self.client.get(reverse('journal:create_plant_entry', args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_empty_form_shows_the_required_banner(self):
        self.client.force_login(self.grower)
        response = self.client.post(self.new_url, {'visibility': 'private'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['missing_required'])
        self.assertContains(response, 'Some required fields are empty. Fill them in to save this entry.')
        self.assertEqual(JournalEntry.objects.count(), 3)

    def test_other_errors_show_the_fixing_banner(self):
        self.client.force_login(self.grower)
        data = self.entry_data(planting=self.tomato.pk, visibility='private', height_cm=-5)
        response = self.client.post(self.new_url, data)
        self.assertFalse(response.context['missing_required'])
        self.assertContains(response, 'Some fields need fixing.')

    def test_bad_upload_shows_the_toast(self):
        self.client.force_login(self.grower)
        data = self.entry_data(
            planting=self.tomato.pk, visibility='private',
            photos=[SimpleUploadedFile('plant.jpg', b'not an image')],
        )
        response = self.client.post(self.new_url, data)
        self.assertIn("Couldn't upload your photo", self.toasts(response))
        self.assertEqual(JournalEntry.objects.count(), 3)
