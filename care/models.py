from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from gardens.models import Planting
from marketplace.models import HarvestListing


class CareTask(models.Model):
    """One planned piece of care for one planting. Only its owner ever sees it."""

    class Activity(models.TextChoices):
        WATERING = 'watering', 'Watering'
        FERTILISING = 'fertilising', 'Fertilising'
        PRUNING = 'pruning', 'Pruning'
        PEST_CHECK = 'pest_check', 'Pest check'
        HARVESTING = 'harvesting', 'Harvesting'
        OTHER = 'other', 'Other'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='care_tasks'
    )
    planting = models.ForeignKey(
        Planting, on_delete=models.CASCADE, related_name='care_tasks'
    )
    activity = models.CharField(
        max_length=20, choices=Activity.choices, default=Activity.WATERING
    )
    planned_for = models.DateField()
    # Without a time the task is simply planned for that day, so the weather check
    # falls back to a summary of the whole day instead of one forecast slot.
    planned_time = models.TimeField(blank=True, null=True)
    notes = models.TextField(blank=True, max_length=500)
    is_done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['planned_for', 'planned_time', 'id']

    def __str__(self):
        return f'{self.get_activity_display()} for {self.planting}'

    def clean(self):
        # A task may only point at a planting in one of the owner's own gardens.
        if self.owner_id and self.planting_id and self.planting.garden.owner_id != self.owner_id:
            raise ValidationError({'planting': 'Choose one of your own plants.'})

    def save(self, *args, **kwargs):
        # completed_at is derived from is_done, so the two can never disagree.
        if self.is_done and self.completed_at is None:
            self.completed_at = timezone.now()
        elif not self.is_done:
            self.completed_at = None
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        return not self.is_done and self.planned_for < timezone.localdate()


class WeatherPreference(models.Model):
    """The limits a grower accepts, used to judge forecast slots."""

    CITY_CHOICES = [(city, city) for city in sorted(HarvestListing.CITY_COORDINATES)]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='weather_preference'
    )
    # Kept here rather than on the shared Profile so this module stays self-contained.
    city = models.CharField(max_length=20, choices=CITY_CHOICES, default='Depok')
    max_rain_mm = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('1.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('50'))],
    )
    max_temperature_c = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('32.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('50'))],
    )
    max_humidity_percent = models.PositiveSmallIntegerField(
        default=85, validators=[MinValueValidator(10), MaxValueValidator(100)]
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Weather preference for {self.user}'

    @classmethod
    def for_user(cls, user):
        preference, _ = cls.objects.get_or_create(user=user)
        return preference

    def accepts(self, slot):
        """True when a forecast hour stays inside all three limits."""
        return (
            slot['rain'] <= float(self.max_rain_mm)
            and slot['temperature'] <= float(self.max_temperature_c)
            and slot['humidity'] <= self.max_humidity_percent
        )
