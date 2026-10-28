from django.db import models

from gardens.models import Planting


class PlantJournal(models.Model):
    planting = models.OneToOneField(Planting, on_delete=models.CASCADE, related_name='journal')
    is_public = models.BooleanField(default=False)

    def __str__(self):
        return f'Journal for {self.planting.crop}'


class JournalEntry(models.Model):
    STAGE_CHOICES = [
        ('seedling', 'Seedling'),
        ('vegetative', 'Vegetative'),
        ('flowering', 'Flowering'),
        ('fruiting', 'Fruiting'),
        ('harvested', 'Harvested'),
    ]
    HEALTH_CHOICES = [
        ('healthy', 'Healthy'),
        ('attention', 'Needs attention'),
        ('pest', 'Pest or disease'),
    ]

    planting = models.ForeignKey(Planting, on_delete=models.CASCADE, related_name='journal_entries')
    date = models.DateField()
    time = models.TimeField()
    height_cm = models.PositiveIntegerField()
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='seedling')
    health = models.CharField(max_length=20, choices=HEALTH_CHOICES, default='healthy')
    observation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']
        verbose_name_plural = 'journal entries'

    def __str__(self):
        return f'{self.planting.crop} on {self.date}'


class EntryPhoto(models.Model):
    # Each photo is either an uploaded file or a link, never both
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='journal/', blank=True)
    url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return self.image.name or self.url

    @property
    def src(self):
        # The address to put in <img src>, whichever kind of photo this is
        return self.image.url if self.image else self.url


