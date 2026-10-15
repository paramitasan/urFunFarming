from django.urls import path

from accounts.views import login_user, logout_user, register

app_name = 'accounts'

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
]
