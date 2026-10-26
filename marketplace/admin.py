from django.contrib import admin

from marketplace.models import HarvestListing


@admin.register(HarvestListing)
class HarvestListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'quantity', 'unit', 'price', 'city', 'is_available', 'is_demo')
    list_filter = ('category', 'city', 'is_available', 'is_demo')
    search_fields = ('title', 'description', 'area', 'owner__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'is_demo')
