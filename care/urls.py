from django.urls import path

from care import views

app_name = 'care'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.create, name='create'),
    path('limits/', views.update_preference, name='limits'),
    path('weather-check/', views.weather_check, name='weather_check'),
    path('<int:pk>/edit/', views.edit, name='edit'),
    path('<int:pk>/delete/', views.delete, name='delete'),
    path('<int:pk>/done/', views.toggle_done, name='toggle_done'),
]
