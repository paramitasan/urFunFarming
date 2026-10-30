from django.contrib import admin
from journal.models import EntryPhoto, JournalEntry, PlantJournal


class EntryPhotoInline(admin.TabularInline):
    model = EntryPhoto
    extra = 1


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('planting', 'date', 'time', 'stage', 'health', 'height_cm')
    list_filter = ('stage', 'health')
    search_fields = ('planting__name', 'planting__crop', 'observation')
    inlines = [EntryPhotoInline]


admin.site.register(PlantJournal)