from django.shortcuts import render
from django.db.models import Count

from .models import Forum

def forum_list(request):
    forums = (
        Forum.objects
        .select_related("author__profile")
        .annotate(reply_count=Count("replies"))
    )

    counts = dict(
        Forum.objects.order_by().values_list("topic").annotate(n=Count("id"))
    )
    topics = [
        {"value": value, "label": label, "count": counts.get(value, 0)}
        for value, label in Forum.Topic.choices
    ]
    
    context = {
        "forums": forums,
        "total": forums.count(),
        "topics": topics,
        "all_count": sum(counts.values()),
    }
    return render(request, "forum/forum_list.html", context)