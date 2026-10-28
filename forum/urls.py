from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.forum_list, name="forum_list"),
    path("add/", views.forum_create, name="forum_create"),
    path("<int:pk>/", views.forum_detail, name="forum_detail"),
    path("<int:pk>/edit/", views.forum_edit, name="forum_edit"),
]