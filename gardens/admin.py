from django.contrib import admin

from gardens.models import Garden, Planting


class PlantingInline(admin.TabularInline):
    model = Planting
    extra = 0


@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'growing_method', 'is_public', 'updated_at')
    list_filter = ('is_public', 'growing_method')
    search_fields = ('name', 'location', 'owner__username')
    inlines = (PlantingInline,)


@admin.register(Planting)
class PlantingAdmin(admin.ModelAdmin):
    list_display = ('crop', 'garden', 'planting_date')
    list_filter = ('planting_date',)
    search_fields = ('crop', 'garden__name', 'garden__owner__username')