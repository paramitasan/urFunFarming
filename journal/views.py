from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from journal.models import PlantJournal, Planting


@login_required(login_url='/login')
def index(request):
    context = {}
    return render(request, 'journal/index.html', context)


def plant_detail(request, planting_id):
    planting = get_object_or_404(Planting, pk=planting_id)
    is_owner = request.user == planting.garden.owner
    is_public = PlantJournal.objects.filter(planting=planting, is_public=True).exists()

    context = {
        'planting': planting,
        'entries': planting.journal_entries.all(),
        'is_owner': is_owner,
        'can_view': is_owner or is_public,
    }
    return render(request, 'journal/plant_detail.html', context)
