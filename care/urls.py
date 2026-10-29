from django.urls import path

from care import views

app_name = 'care'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.create, name='create'),
    path('settings/', views.update_settings, name='settings'),
    path('<int:pk>/edit/', views.edit, name='edit'),
    path('<int:pk>/delete/', views.delete, name='delete'),
    path('<int:pk>/status/', views.change_status, name='status'),
]
