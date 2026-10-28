from django.urls import path

from gardens import views

app_name = 'gardens'

urlpatterns = [
    path('mine/', views.my_gardens, name='mine'),
    path('new/', views.create, name='create'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/edit/', views.edit, name='edit'),
    path('<int:pk>/delete/', views.delete, name='delete'),
]