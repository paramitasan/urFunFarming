from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.contrib.auth.decorators import login_required

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

# Visitors only see titles on the list page, viewing full discussion requires login.
@login_required
def forum_detail(request, pk):
    forum = get_object_or_404(
        Forum.objects.select_related("author__profile"),
        pk=pk,
    )
    replies = forum.replies.select_related("author__profile")

    context = {
        "forum": forum,
        "replies": replies,
    }
    return render(request, "forum/forum_detail.html", context)