"""Read-only forum API, a worked example of protecting endpoints.

GET /api/forum/       open to everyone, like the list page
GET /api/forum/<pk>/  requires login, like the discussion page
"""
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from forum.models import Forum, ForumVote, ReplyVote
from forum.serializers import ForumDetailSerializer, ForumMemberSerializer, ForumVisitorSerializer
from forum.views import FORUM_SORTS, FORUMS_PER_PAGE, REPLY_SORTS, _reply_sort, _with_votes


def _filtered_forums(request):
    # Same query string rules as forum_list: bad values fall back to the default
    params = request.query_params
    user = request.user
    q = params.get('q', '').strip()[:100]
    sort = params.get('sort', 'newest')
    if sort not in FORUM_SORTS:
        sort = 'newest'
    topic = params.get('topic', '')
    if topic not in Forum.Topic.values:
        topic = ''
    show = params.get('show', '')
    if show not in ('answered', 'unanswered', 'mine') or (show == 'mine' and not user.is_authenticated):
        show = ''

    forums = Forum.objects.all()
    for word in q.split():
        match = Q(title__icontains=word)
        if user.is_authenticated:   # visitors only search titles
            match |= Q(description__icontains=word)
        forums = forums.filter(match)

    if show == 'answered':
        forums = forums.filter(is_answered=True)
    elif show == 'unanswered':
        forums = forums.filter(is_answered=False)
    elif show == 'mine':
        forums = forums.filter(author=user)
    if topic:
        forums = forums.filter(topic=topic)

    return _with_votes(
        forums.select_related('author__profile').annotate(reply_count=Count('replies', distinct=True)),
        user, ForumVote, 'forum',
    ).order_by(*FORUM_SORTS[sort])


# No @authentication_classes, so the project defaults apply: a token or a website session
@api_view(['GET'])
@permission_classes([AllowAny])
def forum_list_api(request):
    # Bad page numbers are clamped, as on the website
    page = Paginator(_filtered_forums(request), FORUMS_PER_PAGE).get_page(request.query_params.get('page'))

    # Visitors get the same fields the list page shows them
    serializer_class = ForumMemberSerializer if request.user.is_authenticated else ForumVisitorSerializer
    return Response({
        'count': page.paginator.count,
        'page': page.number,
        'num_pages': page.paginator.num_pages,
        'results': serializer_class(page.object_list, many=True, context={'request': request}).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def forum_detail_api(request, pk):
    forum = get_object_or_404(
        _with_votes(
            Forum.objects.select_related('author__profile').annotate(reply_count=Count('replies', distinct=True)),
            request.user, ForumVote, 'forum',
        ),
        pk=pk,
    )
    replies = _with_votes(
        forum.replies.select_related('author__profile'), request.user, ReplyVote, 'reply',
    ).order_by(*REPLY_SORTS[_reply_sort(request)])

    serializer = ForumDetailSerializer(forum, context={'request': request, 'replies': replies})
    return Response(serializer.data)
