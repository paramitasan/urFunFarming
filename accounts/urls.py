from django.urls import path

from accounts.views import (
    login_ajax, login_user, logout_user, me_json, profile, profile_json, register, register_ajax,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('register/ajax/', register_ajax, name='register_ajax'),
    path('login/ajax/', login_ajax, name='login_ajax'),
    path('profile/', profile, name='profile'),
    path('auth/me/json/', me_json, name='me_json'),
    path('profile/json/<str:username>/', profile_json, name='profile_json'),
]
