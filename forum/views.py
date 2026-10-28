from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count
from django.contrib.auth.decorators import login_required

from .models import Forum
from .forms import ForumForm

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

@login_required
def forum_create(request):
    if request.method == "POST":
        # request.FILES carries the uploaded image
        form = ForumForm(request.POST, request.FILES)
        if form.is_valid():
            forum = form.save(commit=False)
            forum.author = request.user
            forum.save()
            return redirect("forum:forum_detail", pk=forum.pk)
    else:
        form = ForumForm()

    return render(request, "forum/forum_form.html", {"form": form})