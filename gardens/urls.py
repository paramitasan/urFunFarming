from django.urls import path

from gardens import views

app_name = 'gardens'

urlpatterns = [
    path('explore/', views.explore, name='explore'),
    path('explore/<int:pk>/', views.public_detail, name='public_detail'),
    path('mine/', views.my_gardens, name='mine'),
    path('new/', views.create, name='create'),
    path('<int:garden_pk>/plantings/new/', views.planting_create, name='planting_create'),
    path('<int:garden_pk>/plantings/<int:planting_pk>/', views.planting_detail, name='planting_detail'),
    path('<int:garden_pk>/plantings/<int:planting_pk>/edit/', views.planting_edit, name='planting_edit'),
    path('<int:garden_pk>/plantings/<int:planting_pk>/delete/', views.planting_delete, name='planting_delete'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/edit/', views.edit, name='edit'),
    path('<int:pk>/delete/', views.delete, name='delete'),
]