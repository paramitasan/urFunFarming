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
from gardens.models import Garden, Planting
from journal.models import EntryPhoto, JournalEntry, PlantJournal
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
        self.tomato = Planting.objects.create(crop='Cherry Tomato', garden=self.garden, planting_date=date(2026, 9, 5))
        self.chili = Planting.objects.create(crop="Bird's eye chili", garden=self.garden, planting_date=date(2026, 10, 1))
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
        self.assertContains(response, 'This journal is private')
        self.assertNotContains(response, 'First fruits set on the lower truss.')

    def test_private_journal_is_hidden_from_other_growers(self):
        self.client.force_login(self.other_grower)
        response = self.client.get(self.detail_url(self.tomato))
        self.assertContains(response, 'This journal is private')
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
        # Counted from the planting date, not from the first entry
        self.assertEqual(response.context['started_on'], date(2026, 9, 5))
        expected_days = (timezone.localdate() - date(2026, 9, 5)).days
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
        self.assertEqual(response.context['entries'], [])
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
        self.assertContains(response, f'href="{reverse("gardens:detail", args=[self.garden.pk])}"')

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


class EditEntryTest(JournalTestCase):
    def edit_url(self, entry):
        return reverse('journal:edit_entry', args=[entry.pk])

    def toasts(self, response):
        return [str(message) for message in response.context['messages']]

    def unchanged_data(self, **changes):
        # The latest entry exactly as it is saved now
        data = self.entry_data(
            date='2026-10-24', time='07:30', height_cm=92,
            observation='First fruits set on the lower truss.',
        )
        data.update(changes)
        return data

    def test_visitor_is_sent_to_login(self):
        response = self.client.get(self.edit_url(self.latest))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))

    def test_buyer_sees_the_growers_only_page(self):
        self.client.force_login(self.buyer)
        response = self.client.get(self.edit_url(self.latest))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'journal/grower_required.html')

    def test_other_grower_cannot_edit(self):
        self.client.force_login(self.other_grower)
        response = self.client.post(self.edit_url(self.latest), self.unchanged_data(height_cm=1))
        self.assertEqual(response.status_code, 403)
        self.latest.refresh_from_db()
        self.assertEqual(self.latest.height_cm, 92)

    def test_missing_entry_gives_404(self):
        self.client.force_login(self.grower)
        response = self.client.get(reverse('journal:edit_entry', args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_page_is_filled_in_with_the_entry(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.edit_url(self.latest))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.instance, self.latest)
        self.assertNotIn('planting', form.fields)
        self.assertContains(response, 'First fruits set on the lower truss.')
        self.assertContains(response, 'value="07:30"')
        self.assertContains(response, 'Editing the entry from 24 Oct 2026 · 07.30')

    def test_saving_without_changes_says_so(self):
        self.client.force_login(self.grower)
        response = self.client.post(self.edit_url(self.latest), self.unchanged_data(), follow=True)
        self.assertRedirects(response, reverse('journal:plant_detail', args=[self.tomato.pk]))
        self.assertIn('No changes to save', self.toasts(response))

    def test_saving_changes(self):
        self.client.force_login(self.grower)
        data = self.unchanged_data(height_cm=97, health='attention')
        response = self.client.post(self.edit_url(self.latest), data, follow=True)
        self.assertIn('Changes saved', self.toasts(response))
        self.latest.refresh_from_db()
        self.assertEqual(self.latest.height_cm, 97)
        self.assertEqual(self.latest.health, 'attention')
        self.assertEqual(self.latest.planting, self.tomato)

    def test_only_a_new_photo_still_counts_as_a_change(self):
        self.client.force_login(self.grower)
        data = self.unchanged_data(photo_1='https://example.com/tomato.jpg')
        response = self.client.post(self.edit_url(self.latest), data, follow=True)
        self.assertIn('Changes saved', self.toasts(response))
        self.assertEqual(self.latest.photos.count(), 1)

    def test_errors_keep_the_original_date_in_the_header(self):
        self.client.force_login(self.grower)
        response = self.client.post(self.edit_url(self.latest), self.unchanged_data(date=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['original_date'], date(2026, 10, 24))
        self.assertContains(response, 'Editing the entry from 24 Oct 2026 · 07.30')
        self.assertContains(response, 'Fill them in to save your changes.')
        self.latest.refresh_from_db()
        self.assertEqual(self.latest.date, date(2026, 10, 24))

    def test_kept_photos_count_towards_the_limit(self):
        for n in range(4):
            EntryPhoto.objects.create(entry=self.latest, url=f'https://example.com/{n}.jpg')
        self.client.force_login(self.grower)
        data = self.unchanged_data(photo_1='https://example.com/a.jpg', photo_2='https://example.com/b.jpg')
        response = self.client.post(self.edit_url(self.latest), data)
        self.assertContains(response, 'You can add up to 5 photos to one entry.')
        self.assertEqual(self.latest.photos.count(), 4)

    def test_bad_upload_shows_the_toast(self):
        self.client.force_login(self.grower)
        data = self.unchanged_data(photos=[SimpleUploadedFile('plant.jpg', b'not an image')])
        response = self.client.post(self.edit_url(self.latest), data)
        self.assertIn("Couldn't upload your photo", self.toasts(response))


class EditPhotosTest(JournalTestCase):
    def setUp(self):
        super().setUp()
        self.upload = EntryPhoto.objects.create(entry=self.latest, image=make_image('leaf.png'))
        self.link = EntryPhoto.objects.create(entry=self.latest, url='https://example.com/tomato.jpg')
        self.client.force_login(self.grower)

    def edit_url(self):
        return reverse('journal:edit_entry', args=[self.latest.pk])

    def saved_data(self, **changes):
        data = self.entry_data(
            date='2026-10-24', time='07:30', height_cm=92,
            observation='First fruits set on the lower truss.',
        )
        data.update(changes)
        return data

    def test_edit_page_shows_saved_photos_with_remove_boxes(self):
        response = self.client.get(self.edit_url())
        self.assertContains(response, f'src="{self.upload.src}"')
        self.assertContains(response, 'src="https://example.com/tomato.jpg"')
        self.assertContains(response, 'name="remove_photos"', count=2)
        self.assertContains(response, 'Add photo')
        self.assertNotContains(response, 'Drag photos here')

    def test_new_entry_page_keeps_the_dropzone(self):
        response = self.client.get(reverse('journal:create_entry'))
        self.assertContains(response, 'Drag photos here')
        self.assertNotContains(response, 'name="remove_photos"')

    def test_only_this_entrys_photos_can_be_removed(self):
        form = JournalEntryForm(self.grower, instance=self.latest)
        self.assertEqual(set(form.fields['remove_photos'].queryset), {self.upload, self.link})
        self.assertEqual(form.kept_photos, 2)

    def test_removing_photos_deletes_them_and_the_file(self):
        storage = self.upload.image.storage
        file_name = self.upload.image.name
        self.assertTrue(storage.exists(file_name))

        data = self.saved_data(remove_photos=[self.upload.pk, self.link.pk])
        response = self.client.post(self.edit_url(), data, follow=True)
        self.assertIn('Changes saved', [str(m) for m in response.context['messages']])
        self.assertFalse(self.latest.photos.exists())
        self.assertFalse(storage.exists(file_name))

    def test_photo_from_another_entry_cannot_be_removed(self):
        other_photo = EntryPhoto.objects.create(entry=self.first, url='https://example.com/old.jpg')
        response = self.client.post(self.edit_url(), self.saved_data(remove_photos=[other_photo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EntryPhoto.objects.filter(pk=other_photo.pk).exists())

    def test_removing_photos_makes_room_for_new_ones(self):
        for n in range(3):
            EntryPhoto.objects.create(entry=self.latest, url=f'https://example.com/{n}.jpg')
        links = {'photo_1': 'https://example.com/a.jpg', 'photo_2': 'https://example.com/b.jpg'}
        # 5 saved, 2 removed and 2 added makes 5 again
        data = self.saved_data(remove_photos=[self.upload.pk, self.link.pk], **links)
        response = self.client.post(self.edit_url(), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.latest.photos.count(), 5)

    def test_ticked_boxes_stay_ticked_after_an_error(self):
        data = self.saved_data(date='', remove_photos=[self.link.pk])
        response = self.client.post(self.edit_url(), data)
        self.assertEqual(response.context['form']['remove_photos'].value(), [str(self.link.pk)])
        self.assertTrue(EntryPhoto.objects.filter(pk=self.link.pk).exists())


class DeleteEntryTest(JournalTestCase):
    def delete_url(self, entry):
        return reverse('journal:delete_entry', args=[entry.pk])

    def test_owner_deletes_an_entry_with_its_photos(self):
        upload = EntryPhoto.objects.create(entry=self.latest, image=make_image('leaf.png'))
        EntryPhoto.objects.create(entry=self.latest, url='https://example.com/tomato.jpg')
        storage, file_name = upload.image.storage, upload.image.name
        self.client.force_login(self.grower)

        response = self.client.post(self.delete_url(self.latest))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'Entry deleted')
        self.assertEqual(response.json()['plant_url'], reverse('journal:plant_detail', args=[self.tomato.pk]))
        self.assertFalse(JournalEntry.objects.filter(pk=self.latest.pk).exists())
        self.assertFalse(EntryPhoto.objects.exists())
        self.assertFalse(storage.exists(file_name))

    def test_other_grower_gets_a_json_403(self):
        self.client.force_login(self.other_grower)
        response = self.client.post(self.delete_url(self.latest))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['message'], 'You can only delete your own entries.')
        self.assertTrue(JournalEntry.objects.filter(pk=self.latest.pk).exists())

    def test_visitor_gets_a_json_403_not_a_login_page(self):
        response = self.client.post(self.delete_url(self.latest))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_get_is_not_allowed(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.delete_url(self.latest))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(JournalEntry.objects.filter(pk=self.latest.pk).exists())

    def test_missing_entry_gives_404(self):
        self.client.force_login(self.grower)
        response = self.client.post(reverse('journal:delete_entry', args=[999]))
        self.assertEqual(response.status_code, 404)


class DeletePlantEntriesTest(JournalTestCase):
    def delete_url(self, planting):
        return reverse('journal:delete_plant_entries', args=[planting.pk])

    def test_owner_deletes_all_entries_but_keeps_the_plant(self):
        EntryPhoto.objects.create(entry=self.first, url='https://example.com/a.jpg')
        EntryPhoto.objects.create(entry=self.latest, image=make_image('leaf.png'))
        chili_entry = JournalEntry.objects.create(
            planting=self.chili, date=date(2026, 10, 2), time=time(8, 0),
            height_cm=5, observation='Sprouted.',
        )
        self.client.force_login(self.grower)

        response = self.client.post(self.delete_url(self.tomato))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'Entries deleted')
        self.assertEqual(response.json()['detail'], "Cherry Tomato's entries were removed. The plant stays in My gardens.")
        self.assertFalse(self.tomato.journal_entries.exists())
        self.assertFalse(EntryPhoto.objects.exists())
        self.assertTrue(Planting.objects.filter(pk=self.tomato.pk).exists())
        # Another plant's entries are left alone
        self.assertTrue(JournalEntry.objects.filter(pk=chili_entry.pk).exists())

    def test_other_grower_gets_a_json_403(self):
        self.client.force_login(self.other_grower)
        response = self.client.post(self.delete_url(self.tomato))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.tomato.journal_entries.count(), 3)


class DeleteOnTimelineTest(JournalTestCase):
    def detail_url(self):
        return reverse('journal:plant_detail', args=[self.tomato.pk])

    def test_owner_sees_trash_buttons_and_the_dialog(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.detail_url())
        self.assertContains(response, f'data-delete-url="{reverse("journal:delete_entry", args=[self.latest.pk])}"')
        self.assertContains(response, 'Delete this entry?')
        self.assertContains(response, "This entry and its photos will be removed. This can't be undone.")

    def test_others_get_no_trash_buttons_or_dialog(self):
        self.journal.is_public = True
        self.journal.save()
        self.client.force_login(self.buyer)
        response = self.client.get(self.detail_url())
        self.assertNotContains(response, 'data-delete-url')
        self.assertNotContains(response, 'Delete this entry?')

    def test_only_one_new_entry_button_after_the_last_entry_is_deleted(self):
        self.client.force_login(self.grower)
        new_entry_url = reverse('journal:create_plant_entry', args=[self.tomato.pk])
        # With entries, only the header has it. Without, only the empty card does
        self.assertContains(self.client.get(self.detail_url()), new_entry_url, count=1)
        self.client.post(reverse('journal:delete_plant_entries', args=[self.tomato.pk]))
        response = self.client.get(self.detail_url())
        self.assertContains(response, 'No entries yet')
        self.assertContains(response, new_entry_url, count=1)


class DeleteOnEditPageTest(JournalTestCase):
    def test_edit_page_has_the_delete_button_and_dialog(self):
        self.client.force_login(self.grower)
        response = self.client.get(reverse('journal:edit_entry', args=[self.latest.pk]))
        self.assertContains(response, f'data-delete-url="{reverse("journal:delete_entry", args=[self.latest.pk])}"')
        self.assertContains(response, 'Delete this entry?')

    def test_new_entry_page_has_no_delete_dialog(self):
        self.client.force_login(self.grower)
        response = self.client.get(reverse('journal:create_entry'))
        self.assertNotContains(response, 'data-delete-url')
        self.assertNotContains(response, 'Delete this entry?')


class JournalListTest(JournalTestCase):
    list_url = reverse('journal:index')

    def plant(self, crop, day, height=10, stage='seedling', health='healthy', observation='Growing well.'):
        # A plant in Ranu's garden with one entry on the given October day
        planting = Planting.objects.create(crop=crop, garden=self.garden, planting_date=date(2026, 9, 1))
        JournalEntry.objects.create(
            planting=planting, date=date(2026, 10, day), time=time(8, 0), height_cm=height,
            stage=stage, health=health, observation=observation,
        )
        return planting

    def rows(self, response):
        return [row['planting'].crop for row in response.context['page_obj']]

    def test_visitor_is_sent_to_login(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)

    def test_buyer_sees_the_growers_only_page(self):
        self.client.force_login(self.buyer)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_one_row_per_plant_with_its_latest_entry(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.list_url)
        rows = list(response.context['page_obj'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['latest'], self.latest)
        self.assertEqual(rows[0]['entry_count'], 3)
        self.assertContains(response, 'Tebet Rooftop Garden · 3 entries')
        self.assertContains(response, 'Showing 1 plant')
        # The chili has no entries, so it isn't a row
        self.assertNotIn("Bird's eye chili", self.rows(response))

    def test_only_my_own_plants_are_listed(self):
        other_garden = Garden.objects.create(name='Depok Yard', owner=self.other_grower)
        other_plant = Planting.objects.create(crop='Okra', garden=other_garden, planting_date=date(2026, 9, 1))
        JournalEntry.objects.create(planting=other_plant, date=date(2026, 10, 1), time=time(8, 0), height_cm=9, observation='Mine.')
        self.client.force_login(self.grower)
        self.assertEqual(self.rows(self.client.get(self.list_url)), ['Cherry Tomato'])

    def test_search_looks_in_plant_names_and_notes(self):
        self.plant('Thai basil', 20, observation='Pinched the top.')
        self.client.force_login(self.grower)
        self.assertEqual(self.rows(self.client.get(self.list_url, {'q': 'basil'})), ['Thai basil'])
        # 'true leaves' is only in the tomato's oldest entry
        self.assertEqual(self.rows(self.client.get(self.list_url, {'q': 'true leaves'})), ['Cherry Tomato'])

    def test_plant_filter(self):
        basil = self.plant('Thai basil', 20)
        self.client.force_login(self.grower)
        response = self.client.get(self.list_url, {'plant': basil.pk})
        self.assertEqual(self.rows(response), ['Thai basil'])
        self.assertContains(response, 'filter-select is-active')

    def test_stage_and_health_use_the_latest_entry(self):
        self.plant('Pak choy', 20, stage='seedling', health='pest')
        self.client.force_login(self.grower)
        # The tomato had a seedling entry once, but its latest one is fruiting
        self.assertEqual(self.rows(self.client.get(self.list_url, {'stage': 'seedling'})), ['Pak choy'])
        self.assertEqual(self.rows(self.client.get(self.list_url, {'health': 'pest'})), ['Pak choy'])
        self.assertEqual(self.rows(self.client.get(self.list_url, {'stage': 'fruiting', 'health': 'healthy'})), ['Cherry Tomato'])

    def test_no_results_state(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.list_url, {'stage': 'harvested'})
        self.assertContains(response, 'No plants match these filters')
        self.assertContains(response, 'Showing 0 plants')

    def test_a_filter_value_that_is_not_a_choice_is_ignored(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.list_url, {'stage': 'giant'})
        self.assertEqual(self.rows(response), ['Cherry Tomato'])

    def test_sort_options(self):
        self.plant('Basil', 26, height=24)
        self.plant('Zucchini', 1, height=150)
        self.client.force_login(self.grower)
        self.assertEqual(self.rows(self.client.get(self.list_url)), ['Basil', 'Cherry Tomato', 'Zucchini'])
        self.assertEqual(self.rows(self.client.get(self.list_url, {'sort': 'oldest'})), ['Zucchini', 'Cherry Tomato', 'Basil'])
        self.assertEqual(self.rows(self.client.get(self.list_url, {'sort': 'name'})), ['Basil', 'Cherry Tomato', 'Zucchini'])
        self.assertEqual(self.rows(self.client.get(self.list_url, {'sort': 'tallest'})), ['Zucchini', 'Cherry Tomato', 'Basil'])

    def test_ten_plants_per_page_and_links_keep_the_filters(self):
        for day in range(1, 14):
            self.plant(f'Lettuce {day}', day)
        self.client.force_login(self.grower)
        first = self.client.get(self.list_url, {'health': 'healthy'})
        self.assertEqual(len(first.context['page_obj']), 10)
        self.assertContains(first, 'Showing 1–10 of 14 plants')
        self.assertContains(first, 'health=healthy&amp;page=2')

        second = self.client.get(self.list_url, {'health': 'healthy', 'page': 2})
        self.assertEqual(len(second.context['page_obj']), 4)
        self.assertContains(second, 'Showing 11–14 of 14 plants')
        # Rows keep counting from 11 on the second page
        self.assertContains(second, '<td class="cell-no">11</td>', html=True)

    def test_page_number_past_the_end_shows_the_last_page(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.list_url, {'page': 99})
        self.assertEqual(response.context['page_obj'].number, 1)

    def test_lock_shows_private_or_public(self):
        self.client.force_login(self.grower)
        self.assertContains(self.client.get(self.list_url), 'aria-label="Make Cherry Tomato public"')
        self.journal.is_public = True
        self.journal.save()
        self.assertContains(self.client.get(self.list_url), 'aria-label="Make Cherry Tomato private"')

    def test_row_actions_and_delete_dialog(self):
        self.client.force_login(self.grower)
        response = self.client.get(self.list_url)
        self.assertContains(response, reverse('journal:plant_detail', args=[self.tomato.pk]))
        self.assertContains(response, reverse('journal:create_plant_entry', args=[self.tomato.pk]))
        self.assertContains(response, f'data-delete-url="{reverse("journal:delete_plant_entries", args=[self.tomato.pk])}"')
        self.assertContains(response, 'Delete all entries for this plant?')

    def test_empty_state_with_plants_but_no_entries(self):
        JournalEntry.objects.all().delete()
        self.client.force_login(self.grower)
        response = self.client.get(self.list_url)
        self.assertContains(response, 'Start your first entry')
        self.assertNotContains(response, 'data-filter-form')

    def test_empty_state_without_plants(self):
        self.client.force_login(self.other_grower)
        response = self.client.get(self.list_url)
        self.assertContains(response, 'Add a plant to start your journal')
        self.assertContains(response, reverse('gardens:mine'))
        self.assertNotContains(response, reverse('journal:create_entry'))


class ToggleVisibilityTest(JournalTestCase):
    def toggle_url(self, planting):
        return reverse('journal:toggle_visibility', args=[planting.pk])

    def test_owner_switches_private_to_public_and_back(self):
        self.client.force_login(self.grower)
        response = self.client.post(self.toggle_url(self.tomato))
        self.assertEqual(response.json(), {
            'is_public': True,
            'message': 'Cherry Tomato is now public',
            'detail': 'Other growers and buyers can see its journal.',
        })
        self.journal.refresh_from_db()
        self.assertTrue(self.journal.is_public)

        # Pressing it again (or Undo) switches it back
        response = self.client.post(self.toggle_url(self.tomato))
        self.assertEqual(response.json()['message'], 'Cherry Tomato is now private')
        self.assertEqual(response.json()['detail'], 'Only you can see its journal.')
        self.journal.refresh_from_db()
        self.assertFalse(self.journal.is_public)

    def test_plant_without_a_journal_gets_one(self):
        self.client.force_login(self.grower)
        response = self.client.post(self.toggle_url(self.chili))
        self.assertTrue(response.json()['is_public'])
        self.assertTrue(PlantJournal.objects.get(planting=self.chili).is_public)

    def test_other_grower_and_visitor_get_a_json_403(self):
        self.client.force_login(self.other_grower)
        self.assertEqual(self.client.post(self.toggle_url(self.tomato)).status_code, 403)
        self.client.logout()
        response = self.client.post(self.toggle_url(self.tomato))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.journal.refresh_from_db()
        self.assertFalse(self.journal.is_public)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.grower)
        self.assertEqual(self.client.get(self.toggle_url(self.tomato)).status_code, 405)

    def test_list_lock_has_the_toggle_url(self):
        self.client.force_login(self.grower)
        response = self.client.get(reverse('journal:index'))
        self.assertContains(response, f'data-visibility-url="{self.toggle_url(self.tomato)}"')
        self.assertContains(response, 'data-public="false"')
