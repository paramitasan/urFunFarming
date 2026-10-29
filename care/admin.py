from django.contrib import admin

from care.models import CareSettings, CareTask


@admin.register(CareTask)
class CareTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'planting', 'activity', 'target_date', 'target_time', 'status')
    list_filter = ('status', 'activity', 'target_date')
    search_fields = ('title', 'owner__username', 'planting__crop', 'planting__name')
    list_select_related = ('owner', 'planting')
    raw_id_fields = ('owner', 'planting')


@admin.register(CareSettings)
class CareSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'max_rain_mm', 'max_temp_c', 'max_wind_kmh', 'updated_at')
    search_fields = ('user__username',)
