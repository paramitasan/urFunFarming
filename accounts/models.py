from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=50)
    is_grower = models.BooleanField(default=False)
    is_buyer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.display_name} ({self.user.username})'

    @property
    def initials(self):
        # "Muhammad Idris" -> "MI", "Idris" -> "ID"
        words = self.display_name.split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return self.display_name[:2].upper()
