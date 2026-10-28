from django import forms

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