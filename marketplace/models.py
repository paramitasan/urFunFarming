import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from marketplace.dates import jakarta_today


def number_label(value):
    return format(Decimal(value), 'f').rstrip('0').rstrip('.') if Decimal(value) % 1 else str(int(value))


def rupiah(value):
    if not value:
        return 'Free'
    digits = 0 if value % 1 == 0 else 2
    return 'Rp' + f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


class HarvestListingQuerySet(models.QuerySet):
    def public(self):
        return self.filter(
            owner__is_active=True, is_available=True,
        ).filter(Q(available_until__isnull=True) | Q(available_until__gte=jakarta_today()))

    def available_now(self):
        return self.public().filter(available_from__lte=jakarta_today())

    def visible_to(self, user):
        public = Q(owner__is_active=True, is_available=True) & (
            Q(available_until__isnull=True) | Q(available_until__gte=jakarta_today())
        )
        if user.is_authenticated:
            public |= Q(owner=user)
        return self.filter(public)


class HarvestListing(models.Model):
    class Category(models.TextChoices):
        VEGETABLES = 'vegetables', 'Vegetables'
        FRUITS = 'fruits', 'Fruits'
        HERBS = 'herbs', 'Herbs'

    class Unit(models.TextChoices):
        GRAM = 'g', 'g'
        KILOGRAM = 'kg', 'kg'
        BUNCH = 'bunch', 'bunch'
        HEAD = 'head', 'head'
        PIECE = 'piece', 'piece'
        PACK = 'pack', 'pack'

    class City(models.TextChoices):
        DEPOK = 'Depok', 'Depok'
        JAKARTA = 'Jakarta', 'Jakarta'
        BOGOR = 'Bogor', 'Bogor'
        BEKASI = 'Bekasi', 'Bekasi'
        TANGERANG = 'Tangerang', 'Tangerang'

    # Approximate city centres, never private garden or home coordinates.
    CITY_COORDINATES = {
        'Depok': (-6.4025, 106.7942), 'Jakarta': (-6.2088, 106.8456),
        'Bogor': (-6.5971, 106.8060), 'Bekasi': (-6.2383, 106.9756),
        'Tangerang': (-6.1783, 106.6319),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='harvest_listings')
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=2000)
    category = models.CharField(max_length=12, choices=Category.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    unit = models.CharField(max_length=8, choices=Unit.choices)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    price_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1'), validators=[MinValueValidator(Decimal('0.01'))],
    )
    area = models.CharField(max_length=80)
    city = models.CharField(max_length=20, choices=City.choices, default=City.DEPOK)
    image_url = models.URLField(max_length=500, blank=True)
    available_from = models.DateField(default=jakarta_today)
    available_until = models.DateField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    is_demo = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = HarvestListingQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=0), name='harvest_quantity_nonnegative'),
            models.CheckConstraint(condition=Q(price__gte=0), name='harvest_price_nonnegative'),
            models.CheckConstraint(condition=Q(price_quantity__gt=0), name='harvest_price_quantity_positive'),
            models.CheckConstraint(condition=Q(is_available=False) | Q(quantity__gt=0), name='harvest_available_has_stock'),
            models.CheckConstraint(
                condition=Q(available_until__isnull=True) | Q(available_until__gte=models.F('available_from')),
                name='harvest_dates_in_order',
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        if self.available_from and self.available_until and self.available_until < self.available_from:
            errors['available_until'] = 'The end date must be on or after the start date.'
        if self.is_available and self.quantity is not None and self.quantity <= 0:
            errors['quantity'] = 'Available listings need a quantity greater than zero. Pause an empty listing.'
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('marketplace:detail', args=[self.pk])

    def unit_label(self, amount):
        if self.unit in ('g', 'kg') or amount == 1:
            return self.unit
        return {'bunch': 'bunches', 'head': 'heads', 'piece': 'pieces', 'pack': 'packs'}[self.unit]

    @property
    def quantity_label(self):
        return f'{number_label(self.quantity)} {self.unit_label(self.quantity)}'

    @property
    def price_unit_label(self):
        return f'{number_label(self.price_quantity)} {self.unit_label(self.price_quantity)}'

    @property
    def price_label(self):
        return rupiah(self.price)

    @property
    def status_label(self):
        today = jakarta_today()
        if not self.is_available:
            return 'Paused'
        if self.available_until and self.available_until < today:
            return 'Ended'
        if self.available_from > today:
            return f'From {self.available_from:%d %b}'
        return 'Free to collect' if not self.price else 'Available'

    @property
    def grower_name(self):
        profile = getattr(self.owner, 'profile', None)
        return profile.display_name if profile else self.owner.username

    @property
    def grower_initials(self):
        profile = getattr(self.owner, 'profile', None)
        return profile.initials if profile else self.owner.username[:2].upper()
