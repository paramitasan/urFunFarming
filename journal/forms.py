from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

from journal.models import JournalEntry, Planting


class JournalEntryForm(forms.ModelForm):
    photo_1 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)
    photo_2 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)
    photo_3 = forms.URLField(required=False, max_length=500, assume_scheme='https', widget=forms.HiddenInput)

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
            'time': forms.TimeInput(attrs={'type': 'time'}),
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

    def clean_observation(self):
        observation = strip_tags(self.cleaned_data['observation']).strip()
        if not observation:
            raise ValidationError('Please write what you noticed.')
        return observation
    
    def photo_urls(self):
        # The photo links that were filled in, in order, skipping empty ones
        urls = [self.cleaned_data.get(name) for name in ('photo_1', 'photo_2', 'photo_3')]
        return [url for url in urls if url]


class NewEntryForm(JournalEntryForm):
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('public', 'Public'),
    ]

    visibility = forms.ChoiceField(choices=VISIBILITY_CHOICES, initial='private', widget=forms.RadioSelect)
