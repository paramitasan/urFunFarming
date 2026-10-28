from django import forms
from django.core.files.storage import default_storage

from .models import Forum

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/mpo", "image/webp"}


class ForumForm(forms.ModelForm):
    # Declared here so the topic starts on "Select the topic ..." and the user must choose.
    topic = forms.ChoiceField(
        label="Topic",
        choices=[("", "Select the topic of your post")] + list(Forum.Topic.choices),
        error_messages={"required": "Select a topic"},
    )
    remove_image = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Forum
        fields = ["title", "description", "topic", "image"]
        labels = {
            "title": "Title",
            "description": "Description",
            "image": "Upload an image",
        }
        error_messages = {
            "title": {"required": "Title can’t be empty"},
            "description": {"required": "Description can’t be empty"},
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Summary of your post"}),
            "description": forms.Textarea(attrs={"placeholder": "Your question or thoughts", "rows": 4}),
            "image": forms.FileInput(attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "class": "ff-file-input",
            }),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        # Only a fresh upload has content_type.
        # An image already saved on the post has none, so it is skipped.
        if image and hasattr(image, "content_type"):
            if image.content_type not in ALLOWED_IMAGE_TYPES:
                raise forms.ValidationError("Upload a JPG, JPEG, PNG, or WEBP image.")
            if image.size > MAX_IMAGE_BYTES:
                raise forms.ValidationError("Image must be 5 MB or smaller.")
        return image

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_image_name = self.instance.image.name if self.instance.pk else ""
        if self.instance.pk:
            self.fields["image"].label = "Upload new image"

    def save(self, commit=True):
        forum = super().save(commit=False)
        new_upload = bool(self.files.get("image"))
        remove = self.cleaned_data.get("remove_image") and not new_upload

        if remove:
            forum.image = None
        if commit:
            forum.save()
            # Clearing deleted image from media/forum/
            if self._old_image_name and (remove or new_upload):
                default_storage.delete(self._old_image_name)
        return forum