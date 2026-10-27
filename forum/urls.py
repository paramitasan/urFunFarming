from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.forum_list, name="forum_list"),
    path("<int:pk>/", views.forum_detail, name="forum_detail"),
]