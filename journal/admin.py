from django.contrib import admin
from journal.models import EntryPhoto, Garden, JournalEntry, PlantJournal, Planting


class EntryPhotoInline(admin.TabularInline):
    model = EntryPhoto
    extra = 1


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('planting', 'date', 'time', 'stage', 'health', 'height_cm')
    list_filter = ('stage', 'health')
    search_fields = ('planting__name', 'observation')
    inlines = [EntryPhotoInline]


admin.site.register(Garden)
admin.site.register(Planting)
admin.site.register(PlantJournal)