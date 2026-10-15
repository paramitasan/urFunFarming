from django.contrib import admin

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'is_grower', 'is_buyer', 'created_at')
    list_filter = ('is_grower', 'is_buyer')
    search_fields = ('display_name', 'user__username')
