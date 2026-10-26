from django.urls import path

from main.views import filter_listings, home, show_main

app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('home/', home, name='home'),
    path('listings/', filter_listings, name='filter_listings'),
]
