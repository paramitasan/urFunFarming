import calendar

from django import forms

from gardens.models import Garden, Planting


class GardenListFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, strip=True, label='Search my gardens')
    location = forms.CharField(required=False, max_length=120, strip=True, label='Location')
    visibility = forms.ChoiceField(required=False, choices=[
        ('', 'All'), ('public', 'Public'), ('private', 'Private'),
    ])
    sort = forms.ChoiceField(required=False, choices=[
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
    sort = forms.ChoiceField(required=False, choices=[
        ('newest', 'Newest first'), ('oldest', 'Oldest first'), ('name', 'Name A-Z'),
    ], initial='newest')


class PlantingFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, strip=True, label='Search plants')
    month = forms.ChoiceField(required=False, choices=[
        ('', 'Any month'),
        *[(str(month), calendar.month_name[month]) for month in range(1, 13)],
    ])
    method = forms.CharField(required=False, max_length=80, strip=True, label='Growing method')
    sort = forms.ChoiceField(required=False, choices=[
        ('newest', 'Newest planted'), ('oldest', 'Oldest planted'), ('name', 'Name A-Z'),
    ], initial='newest')


class GardenForm(forms.ModelForm):
    class Meta:
        model = Garden
        fields = ('name', 'location', 'growing_method', 'public_summary', 'private_notes', 'is_public')
        labels = {
            'name': 'Garden name',
            'location': 'Location or growing area',
            'growing_method': 'Growing method',
            'public_summary': 'Public summary',
            'private_notes': 'Private notes',
            'is_public': 'Show this garden publicly',
        }
        help_texts = {
            'location': 'Use a neighborhood or general area, not your full home address.',
            'public_summary': 'Shown to visitors when this garden is public.',
            'private_notes': 'Visible only to you.',
        }
        widgets = {
            'public_summary': forms.Textarea(attrs={'rows': 4}),
            'private_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'garden-field'
            if name == 'is_public':
                field.widget.attrs['class'] = 'garden-checkbox'


class PlantingForm(forms.ModelForm):
    class Meta:
        model = Planting
        fields = ('name', 'crop', 'planting_date', 'growing_method')
        labels = {
            'name': 'Plant name',
            'crop': 'Crop',
            'planting_date': 'Planting date',
            'growing_method': 'Growing method',
        }
        help_texts = {
            'name': 'For example Pak choy or Cherry tomato.',
            'crop': 'The kind of crop, for example Leafy greens, Herbs or Fruiting veg.',
            'growing_method': 'Leave blank to use the garden’s method.',
        }
        widgets = {
            'planting_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank is allowed in the database for older plantings, but new ones need a name
        self.fields['name'].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = 'garden-field'
