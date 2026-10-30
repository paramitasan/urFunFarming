from django.contrib import admin

from care.models import CareTask, WeatherPreference


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    list_display = ('activity', 'planting', 'owner', 'planned_for', 'is_done')
    list_filter = ('activity', 'is_done', 'planned_for')
    search_fields = ('notes', 'planting__crop', 'owner__username')
    autocomplete_fields = ()


@admin.register(WeatherPreference)
class WeatherPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'max_rain_mm', 'max_temperature_c', 'max_humidity_percent')
