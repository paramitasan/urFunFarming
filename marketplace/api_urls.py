from django.urls import path

from marketplace.api_views import HarvestDetail, HarvestList, MyHarvests, PickupTimes

app_name = 'marketplace_api'

urlpatterns = [
    path('listings/', HarvestList.as_view(), name='listings'),
    path('mine/', MyHarvests.as_view(), name='mine'),
    path('listings/<uuid:pk>/', HarvestDetail.as_view(), name='detail'),
    path('listings/<uuid:pk>/pickup-weather/', PickupTimes.as_view(), name='weather'),
]
