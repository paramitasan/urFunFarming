from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Forum, Reply
from .forms import ForumForm, ReplyForm

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

@login_required
def forum_create(request):
    if request.method == "POST":
        form = ForumForm(request.POST, request.FILES)
        if form.is_valid():
            forum = form.save(commit=False)
            forum.author = request.user
            forum.save()
            return redirect("forum:forum_detail", pk=forum.pk)
    else:
        form = ForumForm()

    return render(request, "forum/forum_form.html", {"form": form})

def _safe_next(request, default):
    url = request.POST.get("next") or request.GET.get("next", "")
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return default

@login_required
def forum_edit(request, pk):
    forum = get_object_or_404(Forum, pk=pk)

    # Owner check: logged-in users who don't own the post get a 403.
    if forum.author != request.user:
        raise PermissionDenied

    next_url = _safe_next(request, reverse("forum:forum_detail", args=[pk]))
    current_image = forum.image

    if request.method == "POST":
        form = ForumForm(request.POST, request.FILES, instance=forum)
        if form.is_valid():
            form.save()
            return redirect(next_url)
    else:
        form = ForumForm(instance=forum)

    return render(request, "forum/forum_form.html", {
        "form": form,
        "next_url": next_url,
        "current_image": current_image,
        "has_image": bool(current_image) and not form["remove_image"].value(),
    })

@login_required
@require_POST
def forum_delete(request, pk):
    forum = get_object_or_404(Forum, pk=pk)
    if forum.author != request.user:
        raise PermissionDenied

    image = forum.image
    forum.delete()                 # replies go with it (CASCADE)
    image.delete(save=False)       # remove the file from media/forum/

    return redirect(_safe_next(request, reverse("forum:forum_list")))

# Visitors only see titles on the list page, viewing full discussion requires login.
@login_required
def forum_detail(request, pk):
    forum = get_object_or_404(Forum.objects.select_related("author__profile"), pk=pk)
    return _render_detail(request, forum, ReplyForm())

@login_required
@require_POST
def reply_create(request, pk):
    forum = get_object_or_404(Forum.objects.select_related("author__profile"), pk=pk)
    form = ReplyForm(request.POST)
    if form.is_valid():
        reply = form.save(commit=False)
        reply.forum = forum
        reply.author = request.user
        reply.save()
        return redirect(f"{reverse('forum:forum_detail', args=[pk])}#reply-{reply.pk}")
    return _render_detail(request, forum, form)   # shows the error under the box

def _render_detail(request, forum, reply_form, editing=None, edit_form=None):
    context = {
        "forum": forum,
        "replies": forum.replies.select_related("author__profile"),
        "reply_form": reply_form,
        "editing_id": editing.pk if editing else None,
        "edit_form": edit_form,
    }
    return render(request, "forum/forum_detail.html", context)

def _get_own_reply(request, pk):
    # returns reply or a 403 if the current user is not author
    reply = get_object_or_404(
        Reply.objects.select_related("forum__author__profile"), pk=pk
    )
    if reply.author != request.user:
        raise PermissionDenied
    return reply

@login_required
def reply_edit(request, pk):
    reply = _get_own_reply(request, pk)
    forum = reply.forum

    # auto_id keeps this textarea's id different from the "Your answer" box
    if request.method == "POST":
        form = ReplyForm(request.POST, instance=reply, auto_id="id_edit_%s")
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('forum:forum_detail', args=[forum.pk])}#reply-{reply.pk}")
    else:
        form = ReplyForm(instance=reply, auto_id="id_edit_%s")

    return _render_detail(request, forum, ReplyForm(), editing=reply, edit_form=form)

@login_required
@require_POST
def reply_delete(request, pk):
    reply = _get_own_reply(request, pk)
    forum_pk = reply.forum_id
    reply.delete()
    return redirect(f"{reverse('forum:forum_detail', args=[forum_pk])}#answers-heading")