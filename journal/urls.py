from django.urls import path
from journal.views import (
    create_entry, delete_entry, delete_plant_entries, edit_entry, index, plant_detail,
)

app_name = 'journal'

urlpatterns = [
    path('', index, name='index'),
    path('plant/<int:planting_id>/', plant_detail, name='plant_detail'),
    path('new/', create_entry, name='create_entry'),
    path('plant/<int:planting_id>/new/', create_entry, name='create_plant_entry'),
    path('entry/<int:entry_id>/edit/', edit_entry, name='edit_entry'),
    path('entry/<int:entry_id>/delete/', delete_entry, name='delete_entry'),
    path('plant/<int:planting_id>/delete-entries/', delete_plant_entries, name='delete_plant_entries'),
]
