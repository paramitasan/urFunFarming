from django.conf import settings
from django.db import models


class Garden(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gardens')
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=120)
    growing_method = models.CharField(max_length=80)
    public_summary = models.TextField(blank=True)
    private_notes = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class Planting(models.Model):
    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name='plantings')
    crop = models.CharField(max_length=100)
    planting_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-planting_date', 'crop', 'id']

    def __str__(self):
        return f'{self.crop} in {self.garden.name}'