from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from accounts.models import Profile


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
            raise forms.ValidationError('Pick at least one role: growing, buying, or both.')
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
