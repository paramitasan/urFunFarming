from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.http import JsonResponse

from .models import Forum, Reply, ForumVote, ReplyVote
from .forms import ForumForm, ReplyForm

FORUMS_PER_PAGE = 10
FORUM_SORTS = {
    "newest": ("-created_at", "-pk"),
    "oldest": ("created_at", "pk"),
    "answers": ("-reply_count", "-created_at", "-pk"),
    "asked": ("-vote_count", "-created_at", "-pk"),
}

def _list_url(request):
    # list page as user last saw it, with search, filters and page
    return request.session.get("forum_list_url") or reverse("forum:forum_list")

def _with_votes(qs, user, vote_model, field):
    qs = qs.annotate(vote_count=Count("votes", distinct=True))
    if user.is_authenticated:
        qs = qs.annotate(
            user_voted=Exists(vote_model.objects.filter(**{field: OuterRef("pk"), "user": user}))
        )
    return qs


def _toggle_vote(user, vote_model, field, obj):
    _, created = vote_model.objects.get_or_create(**{field: obj, "user": user})
    if not created:
        vote_model.objects.filter(**{field: obj, "user": user}).delete()
    return created

def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"

def forum_list(request):
    # Read and validate query string
    q = request.GET.get("q", "").strip()[:100]
    sort = request.GET.get("sort", "newest")
    if sort not in FORUM_SORTS:
        sort = "newest"
    topic = request.GET.get("topic", "")
    if topic not in Forum.Topic.values:
        topic = ""
    show = request.GET.get("show", "")
    if show not in ("answered", "unanswered", "mine") or (
        show == "mine" and not request.user.is_authenticated
    ):
        show = ""

    # Search and "Show" first, the topic is applied after the counts
    base = Forum.objects.all()
    for word in q.split():
        match = Q(title__icontains=word)
        if request.user.is_authenticated:   # visitors only see titles
            match |= Q(description__icontains=word)
        base = base.filter(match)

    if show == "answered":
        base = base.filter(is_answered=True)
    elif show == "unanswered":
        base = base.filter(is_answered=False)
    elif show == "mine":
        base = base.filter(author=request.user)

    counts = dict(base.order_by().values_list("topic").annotate(n=Count("id")))

    forums = base.filter(topic=topic) if topic else base
    forums = _with_votes(
        forums.select_related("author__profile")
        .annotate(reply_count=Count("replies", distinct=True)),
        request.user, ForumVote, "forum",
    ).order_by(*FORUM_SORTS[sort])

    paginator = Paginator(forums, FORUMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))   # bad page numbers are clamped

    # Query string without "page", so the page links keep the search and filters
    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "page_range": list(
            paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
        ),
        "query": params.urlencode(),
        "total": paginator.count,
        "topics": [
            {"value": value, "label": label, "count": counts.get(value, 0)}
            for value, label in Forum.Topic.choices
        ],
        "all_count": sum(counts.values()),
        "q": q,
        "selected_sort": sort,
        "selected_topic": topic,
        "selected_show": show,
        "is_filtered": bool(q or topic or show),
    }

    if request.user.is_authenticated:
        request.session["forum_list_url"] = request.get_full_path()
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
            if form.has_changed():
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

    return redirect(_safe_next(request, _list_url(request)))

@login_required
@require_POST
def forum_toggle_answered(request, pk):
    forum = get_object_or_404(Forum, pk=pk)
    if forum.author != request.user:
        raise PermissionDenied

    Forum.objects.filter(pk=pk).update(is_answered=not forum.is_answered)
    return redirect(_safe_next(request, reverse("forum:forum_detail", args=[pk])))

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
    return _render_detail(request, forum, form)

REPLY_SORTS = {
    "best": ("-vote_count", "created_at", "pk"),
    "oldest": ("created_at", "pk"),
    "newest": ("-created_at", "-pk"),
}
DEFAULT_REPLY_SORT = "best"

def _reply_sort(request):
    sort = request.GET.get("sort")
    return sort if sort in REPLY_SORTS else DEFAULT_REPLY_SORT


def _detail_url(request, pk, anchor=""):
    # keeps the chosen answer sort
    url = reverse("forum:forum_detail", args=[pk])
    sort = _reply_sort(request)
    if sort != DEFAULT_REPLY_SORT:
        url += f"?sort={sort}"
    return url + anchor


def _render_detail(request, forum, reply_form, editing=None, edit_form=None):
    sort = _reply_sort(request)
    forum = _with_votes(
        Forum.objects.select_related("author__profile"), request.user, ForumVote, "forum"
    ).get(pk=forum.pk)
    replies = _with_votes(
        forum.replies.select_related("author__profile"), request.user, ReplyVote, "reply"
    ).order_by(*REPLY_SORTS[sort])
    
    context = {
        "forum": forum,
        "replies": replies,
        "reply_form": reply_form,
        "editing_id": editing.pk if editing else None,
        "edit_form": edit_form,
        "reply_sort": sort,
        "sort_qs": "" if sort == DEFAULT_REPLY_SORT else f"?sort={sort}",
        "back_url": _list_url(request),
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
            if form.has_changed():
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
    return redirect(_detail_url(request, forum_pk, "#answers-heading"))

@login_required
@require_POST
def forum_vote(request, pk):
    forum = get_object_or_404(Forum, pk=pk)
    voted = _toggle_vote(request.user, ForumVote, "forum", forum)

    if _wants_json(request):
        return JsonResponse({"voted": voted, "count": forum.votes.count()})
    return redirect(f"{_safe_next(request, reverse('forum:forum_detail', args=[pk]))}#forum-{pk}")


@login_required
@require_POST
def reply_vote(request, pk):
    reply = get_object_or_404(Reply, pk=pk)
    voted = _toggle_vote(request.user, ReplyVote, "reply", reply)

    if _wants_json(request):
        return JsonResponse({"voted": voted, "count": reply.votes.count()})
    return redirect(_detail_url(request, reply.forum_id, f"#reply-{pk}"))