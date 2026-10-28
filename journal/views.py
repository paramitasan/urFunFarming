from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Profile
from journal.forms import PHOTO_ERROR, JournalEntryForm, NewEntryForm
from journal.models import EntryPhoto, JournalEntry, PlantJournal, Planting


def is_grower(user):
    # Same lookup as accounts.views.me_json, so a user without a Profile doesn't crash
    profile = Profile.objects.filter(user=user).first()
    return profile is not None and profile.is_grower


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
    
    # First date each stage was reached, going from the oldest entry up
    first_reached = {}
    for entry in reversed(entries):
        first_reached.setdefault(entry.stage, entry.date)

    stage_values = [value for value, label in JournalEntry.STAGE_CHOICES]
    current_index = stage_values.index(entries[0].stage) if entries else -1

    stage_steps = []
    for index, (value, label) in enumerate(JournalEntry.STAGE_CHOICES):
        if index < current_index:
            status = 'done'
        elif index == current_index:
            status = 'current'
        else:
            status = 'next'
        stage_steps.append({'label': label, 'status': status, 'date': first_reached.get(value)})

    context = {
        'planting': planting,
        'entries': entries,
        'is_owner': is_owner,
        'can_view': is_owner or is_public,
        'started_on': started_on,
        'days_growing': days_growing,
        'stage_steps': stage_steps,
    }
    return render(request, 'journal/plant_detail.html', context)


@login_required(login_url='/login')
def create_entry(request, planting_id=None):
    if not is_grower(request.user):
        return render(request, 'journal/grower_required.html', status=403)

    planting = None
    latest = None
    if planting_id is not None:
        # Opened from a plant's page: the plant is fixed and must be the user's own
        planting = get_object_or_404(Planting, pk=planting_id)
        if planting.garden.owner != request.user:
            raise PermissionDenied
        latest = planting.journal_entries.first()
        initial = {'stage': latest.stage} if latest else {}
        form = JournalEntryForm(
            request.user, request.POST or None, request.FILES or None,
            initial=initial, instance=JournalEntry(planting=planting),
        )
        del form.fields['planting']
    else:
        form = NewEntryForm(request.user, request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        entry = form.save()
        for image in form.cleaned_data['photos']:
            EntryPhoto.objects.create(entry=entry, image=image)
        for url in form.photo_urls():
            EntryPhoto.objects.create(entry=entry, url=url)

        journal, _ = PlantJournal.objects.get_or_create(planting=entry.planting)
        # Only the general form has the Private/Public choice
        if 'visibility' in form.cleaned_data:
            journal.is_public = form.cleaned_data['visibility'] == 'public'
            journal.save()

        messages.success(request, 'Entry saved')
        return redirect('journal:plant_detail', planting_id=entry.planting.pk)

    # The banner says "required fields are empty" only when that is really the problem
    missing_required = any(
        error.code == 'required'
        for errors in form.errors.as_data().values()
        for error in errors
    )

    # Bad upload: show the "Couldn't upload your photo" toast as well as the field error
    if PHOTO_ERROR in form.errors.get('photos', []):
        messages.error(request, "Couldn't upload your photo")

    context = {
        'form': form,
        'planting': planting,
        'latest': latest,
        'missing_required': missing_required,
    }
    return render(request, 'journal/entry_form.html', context)
