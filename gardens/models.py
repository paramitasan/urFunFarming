from django.conf import settings
from django.db import models
from django.utils import timezone


class Garden(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gardens')
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=120)
    growing_method = models.CharField(max_length=80)
    public_summary = models.TextField(blank=True)
    private_notes = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    # One thumbnail for the garden card: an uploaded photo or a link to one
    photo = models.ImageField(upload_to='gardens/', blank=True)
    photo_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class Planting(models.Model):
    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name='plantings')
    # Blank on plantings made before these fields existed; display_name and method fall back
    name = models.CharField(max_length=100, blank=True)
    crop = models.CharField(max_length=100)
    planting_date = models.DateField()
    growing_method = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-planting_date', 'crop', 'id']

    def __str__(self):
        return f'{self.display_name} in {self.garden.name}'

    @property
    def display_name(self):
        return self.name or self.crop

    @property
    def method(self):
        return self.growing_method or self.garden.growing_method

    @property
    def day_number(self):
        # "Day 18" badge: days since planting, never negative for a planned date
        return max((timezone.localdate() - self.planting_date).days, 0)