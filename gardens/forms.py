import calendar

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from gardens.models import Garden, Planting

GARDEN_PHOTO_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
GARDEN_PHOTO_FORMATS = ('JPEG', 'PNG', 'WEBP')
GARDEN_PHOTO_ERROR = 'Use a JPG, PNG or WEBP under 5 MB.'


class FallbackChoiceField(forms.ChoiceField):
    # An unknown value (old bookmark, edited URL) falls back to the default instead of failing the form
    def clean(self, value):
        value = self.to_python(value)
        return value if self.valid_value(value) else ''


class GardenListFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, strip=True, label='Search my gardens')
    location = forms.CharField(required=False, max_length=120, strip=True, label='Location')
    visibility = FallbackChoiceField(required=False, choices=[
        ('', 'All'), ('public', 'Public'), ('private', 'Private'),
    ])
    sort = FallbackChoiceField(required=False, choices=[
        ('newest', 'Newest first'), ('oldest', 'Oldest first'), ('name', 'Name A-Z'),
    ])


class GardenExploreFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=100,
        strip=True,
        label='Search gardens',
        widget=forms.SearchInput(attrs={'class': 'garden-field', 'placeholder': 'Search gardens, crops, or areas'}),
    )
    location = forms.CharField(required=False, max_length=120, strip=True, label='Location')
    method = forms.CharField(required=False, max_length=80, strip=True, label='Growing method')
    sort = FallbackChoiceField(required=False, choices=[
        ('newest', 'Newest first'), ('oldest', 'Oldest first'), ('name', 'Name A-Z'),
    ], initial='newest')


class PlantingFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, strip=True, label='Search plants')
    month = FallbackChoiceField(required=False, choices=[
        ('', 'Any month'),
        *[(str(month), calendar.month_name[month]) for month in range(1, 13)],
    ])
    method = forms.CharField(required=False, max_length=80, strip=True, label='Growing method')
    sort = FallbackChoiceField(required=False, choices=[
        ('newest', 'Newest planted'), ('oldest', 'Oldest planted'), ('name', 'Name A-Z'),
    ], initial='newest')


class PhotoFormMixin:
    # Shared by the garden and plant forms: one photo, either uploaded or linked
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        # Only a newly chosen file needs checking, a saved photo was checked when it was uploaded
        if isinstance(photo, UploadedFile):
            # ImageField already opened the file with Pillow, so photo.image.format is the real format
            if photo.size > GARDEN_PHOTO_MAX_SIZE or photo.image.format not in GARDEN_PHOTO_FORMATS:
                raise ValidationError(GARDEN_PHOTO_ERROR)
        return photo

    def clean(self):
        cleaned_data = super().clean()
        new_upload = isinstance(cleaned_data.get('photo'), UploadedFile)
        new_link = bool(cleaned_data.get('photo_url')) and 'photo_url' in self.changed_data
        if new_upload and new_link:
            raise ValidationError('Choose one photo: upload a file or paste a link, not both.')
        # One photo only, so a new upload replaces the link and a new link replaces the upload
        if new_upload:
            cleaned_data['photo_url'] = ''
        elif new_link:
            cleaned_data['photo'] = False
        return cleaned_data


class GardenForm(PhotoFormMixin, forms.ModelForm):
    class Meta:
        model = Garden
        fields = ('name', 'location', 'growing_method', 'public_summary', 'private_notes', 'photo', 'photo_url', 'is_public')
        labels = {
            'name': 'Garden name',
            'location': 'Location or growing area',
            'growing_method': 'Growing method',
            'public_summary': 'Public summary',
            'private_notes': 'Private notes',
            'photo': 'Garden photo',
            'photo_url': 'Or a link to a photo',
            'is_public': 'Show this garden publicly',
        }
        help_texts = {
            'location': 'Use a neighborhood or general area, not your full home address.',
            'public_summary': 'Shown to visitors when this garden is public.',
            'private_notes': 'Visible only to you.',
            'photo': 'One photo for the garden card. JPG, PNG or WEBP, up to 5 MB.',
            'photo_url': 'Paste a link to an image instead of uploading one.',
        }
        widgets = {
            'public_summary': forms.Textarea(attrs={'rows': 4}),
            'private_notes': forms.Textarea(attrs={'rows': 4}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }
        error_messages = {
            'photo': {'invalid_image': GARDEN_PHOTO_ERROR, 'invalid_extension': GARDEN_PHOTO_ERROR},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'garden-field'
            if name == 'is_public':
                field.widget.attrs['class'] = 'garden-checkbox'


class PlantingForm(PhotoFormMixin, forms.ModelForm):
    class Meta:
        model = Planting
        fields = ('name', 'crop', 'planting_date', 'growing_method', 'photo', 'photo_url')
        labels = {
            'name': 'Plant name',
            'crop': 'Crop',
            'planting_date': 'Planting date',
            'growing_method': 'Growing method',
            'photo': 'Plant photo',
            'photo_url': 'Or a link to a photo',
        }
        help_texts = {
            'name': 'For example Pak choy or Cherry tomato.',
            'crop': 'The kind of crop, for example Leafy greens, Herbs or Fruiting veg.',
            'growing_method': 'Leave blank to use the garden’s method.',
            'photo': 'One photo for the plant card. JPG, PNG or WEBP, up to 5 MB.',
            'photo_url': 'Paste a link to an image instead of uploading one.',
        }
        widgets = {
            'planting_date': forms.DateInput(attrs={'type': 'date'}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }
        error_messages = {
            'photo': {'invalid_image': GARDEN_PHOTO_ERROR, 'invalid_extension': GARDEN_PHOTO_ERROR},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank is allowed in the database for older plantings, but new ones need a name
        self.fields['name'].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = 'garden-field'
