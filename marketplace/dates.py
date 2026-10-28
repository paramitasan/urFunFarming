from zoneinfo import ZoneInfo

from django.utils import timezone

JAKARTA = ZoneInfo('Asia/Jakarta')


def jakarta_today():
    """Availability and pickup dates follow the collection location's timezone."""
    return timezone.localdate(timezone=JAKARTA)
