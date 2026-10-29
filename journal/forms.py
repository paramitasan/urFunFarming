from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

from gardens.models import Planting
from journal.models import EntryPhoto, JournalEntry

MAX_PHOTOS = 5
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB
PHOTO_FORMATS = ('JPEG', 'PNG', 'WEBP')
PHOTO_ERROR = 'Use a JPG, PNG or WEBP under 5 MB.'


class MultipleFileInput(forms.ClearableFileInput):
    # Lets the file picker select more than one photo at once
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    # Checks every chosen file like a normal ImageField and returns them as a list
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]
        return [single_file_clean(data, initial)] if data else []


class JournalEntryForm(forms.ModelForm):
    photos = MultipleImageField(
        required=False,
        widget=MultipleFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        error_messages={'invalid_image': PHOTO_ERROR, 'invalid_extension': PHOTO_ERROR},
    )
    photo_1 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)
    photo_2 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)
    photo_3 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)
    photo_4 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)
    photo_5 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)

    # On the edit page, the saved photos the grower ticked to remove
    remove_photos = forms.ModelMultipleChoiceField(
        queryset=EntryPhoto.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
    )

    # Photos the entry already has, so the total stays at 5 or less
    kept_photos = 0

    class Meta:
        model = JournalEntry
        fields = ('planting', 'date', 'time', 'height_cm', 'stage', 'health', 'observation')
        labels = {
            'planting': 'Plant',
            'height_cm': 'Height',
            'stage': 'Growth stage',
            'health': 'Plant health',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'height_cm': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'stage': forms.RadioSelect,
            'health': forms.RadioSelect,
            'observation': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'What did you notice? New leaves, flowers, fruit, pests, color changes...',
            }),
        }
        error_messages = {
            'planting': {'required': 'Please choose a plant.'},
            'date': {'required': 'Please pick a date.'},
            'time': {'required': 'Please enter the time.'},
            'height_cm': {'required': 'Please enter the height in cm.'},
            'observation': {'required': 'Please write what you noticed.'},
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the signed-in grower's own plants can be picked
        self.fields['planting'].queryset = Planting.objects.filter(garden__owner=user)
        self.fields['planting'].empty_label = 'Choose a plant'

        if self.instance.pk:
            # Editing: only this entry's own photos can be removed, and they count towards the limit
            self.fields['remove_photos'].queryset = self.instance.photos.all()
            self.kept_photos = self.instance.photos.count()

    def clean_observation(self):
        observation = strip_tags(self.cleaned_data['observation']).strip()
        if not observation:
            raise ValidationError('Please write what you noticed.')
        return observation
    
    def clean_photos(self):
        photos = self.cleaned_data['photos']
        for photo in photos:
            # ImageField already opened the file with Pillow, so photo.image.format is the real format
            if photo.size > MAX_PHOTO_SIZE or photo.image.format not in PHOTO_FORMATS:
                raise ValidationError(PHOTO_ERROR)
        return photos

    def clean(self):
        cleaned_data = super().clean()
        kept = self.kept_photos - len(cleaned_data.get('remove_photos') or [])
        total = kept + len(cleaned_data.get('photos') or []) + len(self.photo_urls())
        if total > MAX_PHOTOS:
            self.add_error('photos', f'You can add up to {MAX_PHOTOS} photos to one entry.')
        return cleaned_data

    def photo_urls(self):
        # The photo links that were filled in, in order, skipping empty ones
        names = ['photo_1', 'photo_2', 'photo_3', 'photo_4', 'photo_5']
        urls = [self.cleaned_data.get(name) for name in names]
        return [url for url in urls if url]


class NewEntryForm(JournalEntryForm):
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('public', 'Public'),
    ]

    visibility = forms.ChoiceField(choices=VISIBILITY_CHOICES, initial='private', widget=forms.RadioSelect)
