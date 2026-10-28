from django.urls import path
from journal.views import index, plant_detail

app_name = 'journal'

urlpatterns = [
    path('', index, name='index'),
    path('plant/<int:planting_id>/', plant_detail, name='plant_detail'),
]
