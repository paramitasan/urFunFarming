from datetime import time, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from django import forms

from marketplace.dates import jakarta_today
from marketplace.models import HarvestListing


class ListingForm(forms.ModelForm):
    image_url = forms.URLField(
        required=False, max_length=500, assume_scheme='https', label='Photo URL',
        help_text='Optional. Use a public HTTPS or HTTP image link.',
    )

    class Meta:
        model = HarvestListing
        fields = (
            'title', 'description', 'category', 'quantity', 'unit', 'price', 'price_quantity',
            'area', 'city', 'image_url', 'available_from', 'available_until', 'is_available',
        )
        labels = {
            'quantity': 'Available quantity', 'price': 'Price (Rp)', 'price_quantity': 'Quantity per price',
            'area': 'Collection area', 'available_from': 'Available from', 'available_until': 'Available until',
            'is_available': 'This harvest is available',
        }
        help_texts = {
            'price': 'Enter 0 to offer your harvest for free.',
            'price_quantity': 'Example: Rp15.000 for 500 g. Use the same unit as the available quantity.',
            'area': 'A neighborhood or public collection area, rather than your full home address.',
            'available_until': 'Optional. Expired offers are removed from public browsing.',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'available_from': forms.DateInput(attrs={'type': 'date'}),
            'available_until': forms.DateInput(attrs={'type': 'date'}),
            'quantity': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'price_quantity': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'market-input'
            field.widget.attrs['aria-describedby'] = f'id_{name}_help id_{name}_error'
            if self.is_bound and name in self.errors:
                field.widget.attrs['aria-invalid'] = 'true'

    def clean_image_url(self):
        value = self.cleaned_data['image_url']
        if value and urlsplit(value).scheme not in ('http', 'https'):
            raise forms.ValidationError('Use an HTTP or HTTPS image link.')
        return value


class ListingFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=120, strip=True)
    category = forms.ChoiceField(required=False, choices=[('', 'All produce'), *HarvestListing.Category.choices])
    availability = forms.ChoiceField(choices=[('now', 'Available now'), ('any', 'Any time')])
    price_type = forms.ChoiceField(required=False, choices=[('', 'Any price'), ('free', 'Free'), ('paid', 'Paid')])
    max_price = forms.DecimalField(required=False, min_value=0, max_value=Decimal('9999999999.99'), decimal_places=2)
    city = forms.ChoiceField(required=False, choices=[('', 'All areas'), *HarvestListing.City.choices])
    area = forms.CharField(required=False, max_length=80)
    grower = forms.CharField(required=False, max_length=150)
    sort = forms.ChoiceField(required=False, choices=[
        ('newest', 'Newest first'), ('price_asc', 'Price: low to high'),
        ('price_desc', 'Price: high to low'), ('title', 'Name: A to Z'),
    ])


class PickupWeatherForm(forms.Form):
    date = forms.DateField(initial=jakarta_today, widget=forms.DateInput(attrs={'type': 'date'}))
    start_time = forms.TimeField(initial=time(8), widget=forms.TimeInput(attrs={'type': 'time'}))
    end_time = forms.TimeField(initial=time(18), widget=forms.TimeInput(attrs={'type': 'time'}))
    max_rain = forms.DecimalField(
        label='Maximum rain (mm)', min_value=0, max_value=100, decimal_places=2, initial=Decimal('1'),
        widget=forms.NumberInput(attrs={'step': '0.1'}),
    )
    max_temperature = forms.DecimalField(
        label='Maximum temperature (°C)', min_value=-10, max_value=60, decimal_places=1, initial=Decimal('35'),
        widget=forms.NumberInput(attrs={'step': '0.5'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'market-input'
            field.widget.attrs['id'] = f'weather_{name}'
        self.fields['date'].widget.attrs.update(min=jakarta_today().isoformat(), max=(jakarta_today() + timedelta(days=2)).isoformat())

    def clean_date(self):
        value = self.cleaned_data['date']
        # BMKG forecasts cover today and the next two days
        if not jakarta_today() <= value <= jakarta_today() + timedelta(days=2):
            raise forms.ValidationError('Choose a date within the next 3 days.')
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('start_time') and cleaned.get('end_time') and cleaned['start_time'] > cleaned['end_time']:
            raise forms.ValidationError('The end time must be after the start time.')
        return cleaned
