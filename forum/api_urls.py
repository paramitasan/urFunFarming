from django.urls import path

from forum.api_views import forum_detail_api, forum_list_api

app_name = 'forum_api'

urlpatterns = [
    path('', forum_list_api, name='forum_list'),
    path('<int:pk>/', forum_detail_api, name='forum_detail'),
]
