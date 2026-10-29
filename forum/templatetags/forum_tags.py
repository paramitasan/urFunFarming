from django import template
from django.db.models import Count

from forum.models import Forum

register = template.Library()

@register.simple_tag
def recent_forums(limit=5):
    # most recent questions, returns fewer if fewer exist
    return (
        Forum.objects
        .annotate(reply_count=Count("replies"))
        .order_by("-created_at", "-pk")[:limit]
    )