from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from journal.models import PlantJournal, Planting


@login_required(login_url='/login')
def index(request):
    context = {}
    return render(request, 'journal/index.html', context)


def plant_detail(request, planting_id):
    planting = get_object_or_404(Planting, pk=planting_id)
    is_owner = request.user == planting.garden.owner
    is_public = PlantJournal.objects.filter(planting=planting, is_public=True).exists()

    # Newest first, so the entry after each one in the list is the one before it in time
    entries = list(planting.journal_entries.all())
    for i, entry in enumerate(entries):
        if i + 1 < len(entries):
            entry.height_change = entry.height_cm - entries[i + 1].height_cm
        else:
            entry.height_change = None

    started_on = entries[-1].date if entries else None
    days_growing = (timezone.localdate() - started_on).days if started_on else None

    context = {
        'planting': planting,
        'entries': entries,
        'is_owner': is_owner,
        'can_view': is_owner or is_public,
        'started_on': started_on,
        'days_growing': days_growing,
    }
    return render(request, 'journal/plant_detail.html', context)
