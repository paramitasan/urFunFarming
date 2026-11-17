from django.urls import path

from accounts.api_views import login_api, logout_api, me_api, register_api

app_name = 'accounts_api'

urlpatterns = [
    path('register/', register_api, name='register'),
    path('login/', login_api, name='login'),
    path('logout/', logout_api, name='logout'),
    path('me/', me_api, name='me'),
]
