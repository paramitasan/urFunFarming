from django.urls import path
from journal.views import index

app_name = 'journal'

urlpatterns = [
    path('', index, name='index'),
]
