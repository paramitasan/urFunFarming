from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from gardens.models import Planting
from weather.services import meets_thresholds


class CareTask(models.Model):
    class Activity(models.TextChoices):
        WATER = 'water', 'Water'
        FERTILIZE = 'fertilize', 'Fertilize'
        PRUNE = 'prune', 'Prune'
        CHECK_PH = 'check_ph', 'Check pH'
        HARVEST = 'harvest', 'Harvest'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        TODO = 'todo', 'To do'
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='care_tasks')
    planting = models.ForeignKey(Planting, on_delete=models.CASCADE, related_name='care_tasks')
    activity = models.CharField(max_length=20, choices=Activity.choices, default=Activity.WATER)
    title = models.CharField(max_length=120)
    # Completion target: a date, with an optional time
    target_date = models.DateField()
    target_time = models.TimeField(null=True, blank=True)
    # Private: only the owner ever sees these
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target_date', 'target_time', 'id']

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'

    def clean(self):
        # A task can only point at one of the owner's own plantings
        if self.owner_id and self.planting_id and self.planting.garden.owner_id != self.owner_id:
            raise ValidationError({'planting': 'Choose one of your own plantings.'})


class CareSettings(models.Model):
    """A grower's weather limits. A forecast slot is "good" when it is within all three."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='care_settings')
    max_rain_mm = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('2'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    max_temp_c = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('32'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('50'))],
    )
    max_wind_kmh = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('15'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('150'))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'care settings'

    def __str__(self):
        return f'Care settings for {self.user}'

    @classmethod
    def for_user(cls, user):
        # Every grower starts with the defaults until they change them
        settings_row, _ = cls.objects.get_or_create(user=user)
        return settings_row

    def is_good(self, slot):
        return meets_thresholds(slot, self.max_rain_mm, self.max_temp_c, self.max_wind_kmh)
