from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User

from accounts.locations import find_village, village_choices
from accounts.models import Profile

ROLE_ERROR = 'Pick at least one role: growing, buying, or both.'


class RegisterForm(UserCreationForm):
    display_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'How neighbors will see you'}),
    )
    is_grower = forms.BooleanField(required=False, label='I grow food')
    is_buyer = forms.BooleanField(required=False, label='I buy local produce')

    class Meta:
        model = User
        fields = ('display_name', 'username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'Letters, numbers and _ only'
        self.fields['password1'].widget.attrs['placeholder'] = '8+ characters'
        self.fields['password2'].widget.attrs['placeholder'] = 'Type it again'
        self.fields['password2'].label = 'Confirm password'

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('is_grower') and not cleaned_data.get('is_buyer'):
            raise forms.ValidationError(ROLE_ERROR)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Profile.objects.create(
                user=user,
                display_name=self.cleaned_data['display_name'],
                is_grower=self.cleaned_data['is_grower'],
                is_buyer=self.cleaned_data['is_buyer'],
            )
        return user


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': "That username and password don't match. Check them and try again.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'e.g. idris_k'
        self.fields['password'].widget.attrs['placeholder'] = 'Your password'


class ProfileForm(forms.ModelForm):
    # Replaces typing an area and city: pick a village, and the area (district), city and
    # BMKG village code are filled in from accounts/data/jabodetabek.json
    location = forms.ChoiceField(
        required=False,
        label='Your area',
        help_text='Used for local weather. Others see only the district and city, never your address.',
    )

    class Meta:
        model = Profile
        fields = ('display_name', 'bio', 'phone', 'contact_email', 'is_grower', 'is_buyer')
        labels = {
            'phone': 'WhatsApp or phone',
            'contact_email': 'Email',
            'is_grower': 'I grow food',
            'is_buyer': 'I buy local produce',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What you grow, where, and what you like to swap'}),
            'phone': forms.TextInput(attrs={'placeholder': '+62 812 3456 7890', 'autocomplete': 'tel'}),
            'contact_email': forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].choices = village_choices()
        self.fields['location'].initial = self.instance.adm4_code

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('is_grower') and not cleaned_data.get('is_buyer'):
            raise forms.ValidationError(ROLE_ERROR)
        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        place = find_village(self.cleaned_data.get('location'))
        # No area chosen clears the old one, so what you see is what is saved
        profile.adm4_code = place['code'] if place else ''
        profile.area = place['district'] if place else ''
        profile.city = place['city'] if place else ''
        if commit:
            profile.save()
        return profile


class PasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Current password'
        self.fields['old_password'].widget.attrs['placeholder'] = 'Your current password'
        self.fields['old_password'].widget.attrs.pop('autofocus', None)
        self.fields['new_password1'].widget.attrs['placeholder'] = '8+ characters'
        self.fields['new_password2'].widget.attrs['placeholder'] = 'Type it again'
        self.fields['new_password2'].label = 'Confirm new password'
