from django import forms

from care.models import CareSettings, CareTask
from gardens.forms import FallbackChoiceField
from gardens.models import Planting

STATUS_FILTERS = [
    ('todo', 'To do'),
    ('in_progress', 'In progress'),
    ('completed', 'Completed'),
    ('all', 'All'),
]

SORTS = [
    ('soonest', 'Soonest first'),
    ('latest', 'Latest first'),
    ('plant', 'Plant A-Z'),
    ('newest', 'Recently added'),
]


class TaskFilterForm(forms.Form):
    # Unknown values from an edited URL fall back to the defaults
    status = FallbackChoiceField(required=False, choices=STATUS_FILTERS)
    sort = FallbackChoiceField(required=False, choices=SORTS)


class PlantingChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, planting):
        # "Cherry tomato · Balcony rack, Tebet"
        return f'{planting.display_name} · {planting.garden.name}, {planting.garden.location}'


class CareTaskForm(forms.ModelForm):
    planting = PlantingChoiceField(queryset=Planting.objects.none(), empty_label='Choose a planting')

    class Meta:
        model = CareTask
        fields = ('activity', 'planting', 'title', 'target_date', 'target_time', 'notes', 'status')
        labels = {
            'target_date': 'Completion target',
            'target_time': 'Time',
            'notes': 'Notes (private)',
        }
        help_texts = {
            'title': 'Leave blank to use the activity and plant, like "Water Cherry tomato".',
            'target_time': 'Optional.',
            'notes': 'Only you can see your notes and tasks.',
            'status': 'New tasks start as "To do". Move them to "In progress" and "Completed" as you go.',
        }
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'target_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the grower's own plantings can be picked; anything else fails validation
        self.fields['planting'].queryset = (
            Planting.objects.filter(garden__owner=user).select_related('garden').order_by('garden__name', 'crop', 'id')
        )
        self.fields['title'].required = False
        # Set before validation so the model's own-planting check runs too
        self.instance.owner = user

    def clean_title(self):
        return self.cleaned_data['title'].strip()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('title') and cleaned.get('activity') and cleaned.get('planting'):
            activity = CareTask.Activity(cleaned['activity']).label
            cleaned['title'] = f'{activity} {cleaned["planting"].display_name}'
            self.instance.title = cleaned['title']
        elif not cleaned.get('title'):
            self.add_error('title', 'Give the task a title.')
        return cleaned


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=CareTask.Status.choices)


class CareSettingsForm(forms.ModelForm):
    class Meta:
        model = CareSettings
        fields = ('max_rain_mm', 'max_temp_c', 'max_wind_kmh')
        labels = {
            'max_rain_mm': 'Max rain',
            'max_temp_c': 'Max temperature',
            'max_wind_kmh': 'Max wind',
        }
        widgets = {
            'max_rain_mm': forms.NumberInput(attrs={'step': '0.5', 'min': '0'}),
            'max_temp_c': forms.NumberInput(attrs={'step': '0.5', 'min': '0'}),
            'max_wind_kmh': forms.NumberInput(attrs={'step': '1', 'min': '0'}),
        }
