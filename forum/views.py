from django.shortcuts import render
from django.db.models import Count

from .models import Forum

def forum_list(request):
    forums = (
        Forum.objects
        .select_related("author__profile")
        .annotate(reply_count=Count("replies"))
    )
    context = {
        "forums": forums,
        "total": forums.count(),
    }
    return render(request, "forum/forum_list.html", context)