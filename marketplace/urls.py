from django.urls import path

from marketplace import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.index, name='index'),
    path('mine/', views.my_listings, name='mine'),
    path('new/', views.create, name='create'),
    path('api/listings/', views.listings_json, name='listings_json'),
    path('api/listings/<uuid:pk>/', views.listing_json, name='listing_json'),
    path('<uuid:pk>/', views.detail, name='detail'),
    path('<uuid:pk>/edit/', views.edit, name='edit'),
    path('<uuid:pk>/delete/', views.delete, name='delete'),
    path('<uuid:pk>/weather/', views.pickup_weather, name='weather'),
]
