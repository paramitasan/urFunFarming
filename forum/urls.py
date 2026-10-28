from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.forum_list, name="forum_list"),
    path("add/", views.forum_create, name="forum_create"),
    path("<int:pk>/", views.forum_detail, name="forum_detail"),
    path("<int:pk>/edit/", views.forum_edit, name="forum_edit"),
    path("<int:pk>/delete/", views.forum_delete, name="forum_delete"),
    path("<int:pk>/answered/", views.forum_toggle_answered, name="forum_toggle_answered"),

    path("<int:pk>/replies/add/", views.reply_create, name="reply_create"),
    path("replies/<int:pk>/edit/", views.reply_edit, name="reply_edit"),
    path("replies/<int:pk>/delete/", views.reply_delete, name="reply_delete"),

    path("<int:pk>/vote/", views.forum_vote, name="forum_vote"),
    path("replies/<int:pk>/vote/", views.reply_vote, name="reply_vote"),
]