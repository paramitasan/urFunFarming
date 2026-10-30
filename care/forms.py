from django import forms

from care.models import CareTask, WeatherPreference
from gardens.models import Planting


class CareTaskForm(forms.ModelForm):
    class Meta:
        model = CareTask
        fields = ['planting', 'activity', 'planned_for', 'planned_time', 'notes']
        labels = {
            'planting': 'Plant',
            'planned_for': 'Planned date',
            'planned_time': 'Planned time (optional)',
            'notes': 'Private notes (optional)',
        }
        widgets = {
            'planned_for': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'planned_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Only you can read this'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # The dropdown may only ever offer plants from the grower's own gardens.
        # Doing it here means the restriction also holds when the form is posted.
        self.fields['planting'].queryset = (
            Planting.objects.filter(garden__owner=user)
            .select_related('garden')
            .order_by('garden__name', 'crop')
        )
        self.fields['planting'].empty_label = 'Choose one of your plants'


class WeatherPreferenceForm(forms.ModelForm):
    class Meta:
        model = WeatherPreference
        fields = ['city', 'max_rain_mm', 'max_temperature_c', 'max_humidity_percent']
        labels = {
            'city': 'City',
            'max_rain_mm': 'Rain at most (mm per hour)',
            'max_temperature_c': 'Temperature at most (degrees)',
            'max_humidity_percent': 'Humidity at most (percent)',
        }


class CareTaskFilterForm(forms.Form):
    """Read-only form over the GET parameters of the task list."""

    SHOW_CHOICES = [
        ('open', 'Open'),
        ('done', 'Done'),
        ('overdue', 'Overdue'),
        ('all', 'All'),
    ]
    SORT_CHOICES = [
        ('soonest', 'Soonest first'),
        ('latest', 'Latest first'),
        ('added', 'Recently added'),
    ]

    show = forms.ChoiceField(choices=SHOW_CHOICES, required=False)
    activity = forms.ChoiceField(choices=[('', 'Any activity')] + CareTask.Activity.choices, required=False)
    planting = forms.ModelChoiceField(queryset=Planting.objects.none(), required=False, empty_label='Any plant')
    sort = forms.ChoiceField(choices=SORT_CHOICES, required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['planting'].queryset = Planting.objects.filter(garden__owner=user).select_related('garden')

    def clean_show(self):
        # An unknown value in the URL falls back to the default instead of erroring.
        return self.cleaned_data.get('show') or 'open'

    def clean_sort(self):
        return self.cleaned_data.get('sort') or 'soonest'
