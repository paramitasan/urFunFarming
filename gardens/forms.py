from django import forms

from gardens.models import Garden


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
