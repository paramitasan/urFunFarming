from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import Profile
from gardens.models import Planting
from journal.forms import PHOTO_ERROR, JournalEntryForm, JournalFilterForm, NewEntryForm
from journal.models import EntryPhoto, JournalEntry, PlantJournal


def is_grower(user):
    # Same lookup as accounts.views.me_json, so a user without a Profile doesn't crash
    profile = Profile.objects.filter(user=user).first()
    return profile is not None and profile.is_grower


def display_name(user):
    # The name other people see, falling back to the username if there's no Profile
    profile = Profile.objects.filter(user=user).first()
    return profile.display_name if profile and profile.display_name else user.username


def save_new_photos(entry, form):
    # Uploads first, then links, as new EntryPhoto rows for this entry
    for image in form.cleaned_data['photos']:
        EntryPhoto.objects.create(entry=entry, image=image)
    for url in form.photo_urls():
        EntryPhoto.objects.create(entry=entry, url=url)


def delete_photos(photos):
    # Removes the photos and their uploaded files, so nothing is left behind in media/
    for photo in photos:
        photo.image.delete(save=False)
        photo.delete()


def has_missing_required(form):
    # True when at least one required field was left empty
    return any(
        error.code == 'required'
        for errors in form.errors.as_data().values()
        for error in errors
    )


@login_required(login_url='/login')
def index(request):
    if not is_grower(request.user):
        # The journal pages don't exist for buyers, they only see public plant pages
        raise Http404

    form = JournalFilterForm(request.user, request.GET)
    # A filter value that isn't one of the choices (typed into the address bar) is ignored
    filters = form.cleaned_data if form.is_valid() else {}

    my_plants = Planting.objects.filter(garden__owner=request.user)

    # One row per plant with its latest entry. The database works out the latest entry and the count,
    # so filtering, sorting and paging happen there and only this page's entries are loaded
    entries = JournalEntry.objects.filter(planting=OuterRef('pk')).order_by('-date', '-time', '-id')
    entry_count = JournalEntry.objects.filter(planting=OuterRef('pk')).values('planting').annotate(n=Count('pk')).values('n')
    plants = my_plants.annotate(
        latest_id=Subquery(entries.values('pk')[:1]),
        latest_stage=Subquery(entries.values('stage')[:1]),
        latest_health=Subquery(entries.values('health')[:1]),
        latest_date=Subquery(entries.values('date')[:1]),
        latest_time=Subquery(entries.values('time')[:1]),
        latest_height=Subquery(entries.values('height_cm')[:1]),
        entry_count=Subquery(entry_count),
    ).filter(latest_id__isnull=False)
    if filters.get('plant'):
        plants = plants.filter(pk=filters['plant'].pk)
    if filters.get('q'):
        query = filters['q']
        notes = JournalEntry.objects.filter(planting=OuterRef('pk'), observation__icontains=query)
        plants = plants.filter(Q(name__icontains=query) | Q(crop__icontains=query) | Exists(notes))
    # Stage and health are checked on each plant's latest entry
    if filters.get('stage'):
        plants = plants.filter(latest_stage=filters['stage'])
    if filters.get('health'):
        plants = plants.filter(latest_health=filters['health'])

    sort = filters.get('sort') or 'recent'
    order = {
        # Same fallback as Planting.display_name
        'name': (Lower(Coalesce(NullIf('name', Value('')), 'crop')), 'pk'),
        'tallest': ('-latest_height', 'pk'),
        'oldest': ('latest_date', 'latest_time', 'latest_id'),
    }.get(sort, ('-latest_date', '-latest_time', '-latest_id'))
    plants = plants.select_related('garden').order_by(*order)

    paginator = Paginator(plants, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    latest_entries = JournalEntry.objects.in_bulk([planting.latest_id for planting in page_obj])
    page_obj.object_list = [
        {'planting': planting, 'latest': latest_entries[planting.latest_id], 'entry_count': planting.entry_count}
        for planting in page_obj
    ]
    count_label = f'Showing {paginator.count} plant{"" if paginator.count == 1 else "s"}'

    # The page links keep the current filters, only the page number changes
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'form': form,
        'page_obj': page_obj,
        'count_label': count_label,
        'querystring': params.urlencode(),
        'public_ids': set(PlantJournal.objects.filter(planting__in=my_plants, is_public=True).values_list('planting_id', flat=True)),
        'has_plants': my_plants.exists(),
        'has_entries': JournalEntry.objects.filter(planting__in=my_plants).exists(),
        'nav_active': 'home',
    }
    return render(request, 'journal/index.html', context)


def plant_detail(request, planting_id):
    planting = get_object_or_404(Planting.objects.select_related('garden__owner'), pk=planting_id)
    garden = planting.garden
    is_owner = request.user == garden.owner

    # Same rule as the Gardens plant page: other people only see plants of a public garden whose
    # owner is still active, anyone else gets the shared "No access" page without any details
    if not is_owner and not (garden.is_public and garden.owner.is_active):
        return render(request, 'gardens/planting_detail.html', {'no_access': True, 'nav_active': 'explore'}, status=403)

    is_public = PlantJournal.objects.filter(planting=planting, is_public=True).exists()
    if is_owner:
        garden_url = reverse('gardens:detail', args=[garden.pk])
    else:
        garden_url = reverse('gardens:public_detail', args=[garden.pk])

    # Newest first, so the entry after each one in the list is the one before it in time.
    # The photos come in one query for the whole timeline instead of one per entry
    entries = list(planting.journal_entries.prefetch_related('photos'))
    for i, entry in enumerate(entries):
        if i + 1 < len(entries):
            entry.height_change = entry.height_cm - entries[i + 1].height_cm
        else:
            entry.height_change = None

    started_on = planting.planting_date
    # Same count as the "Day N" badge in Gardens, so a planned (future) date shows 0, not a negative
    days_growing = planting.day_number

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

    # ?order=oldest flips only the timeline, the rest of the page still reads entries newest first
    oldest_first = request.GET.get('order') == 'oldest'
    timeline = list(reversed(entries)) if oldest_first else entries

    context = {
        'planting': planting,
        'entries': entries,
        'timeline': timeline,
        'oldest_first': oldest_first,
        'is_owner': is_owner,
        'can_view': is_owner or is_public,
        'grower_name': display_name(garden.owner),
        'garden_url': garden_url,
        'started_on': started_on,
        'days_growing': days_growing,
        'stage_steps': stage_steps,
        # Opened from the garden page: the back link returns there instead of to the journal
        'from_garden': request.GET.get('from') == 'garden',
        # The owner is in their own space (Home), anyone else came from Explore gardens
        'nav_active': 'home' if is_owner else 'explore',
    }
    return render(request, 'journal/plant_detail.html', context)


@login_required(login_url='/login')
def create_entry(request, planting_id=None):
    if not is_grower(request.user):
        # The journal pages don't exist for buyers, they only see public plant pages
        raise Http404

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
        save_new_photos(entry, form)

        journal, _ = PlantJournal.objects.get_or_create(planting=entry.planting)
        # Only the general form has the Private/Public choice, and an empty choice keeps the current one
        if form.cleaned_data.get('visibility'):
            journal.is_public = form.cleaned_data['visibility'] == 'public'
            journal.save()

        messages.success(request, 'Entry saved')
        # Started from the + on the journal list: go back to the list
        if request.GET.get('from') == 'list':
            return redirect('journal:index')
        return redirect('journal:plant_detail', planting_id=entry.planting.pk)
        return redirect('journal:plant_detail', planting_id=entry.planting.pk)

    # Bad upload: show the "Couldn't upload your photo" toast as well as the field error
    if PHOTO_ERROR in form.errors.get('photos', []):
        messages.error(request, "Couldn't upload your photo", extra_tags=PHOTO_ERROR)

    context = {
        'form': form,
        'planting': planting,
        'latest': latest,
        'missing_required': has_missing_required(form),
        'nav_active': 'home',
        'from_list': request.GET.get('from') == 'list',
        # entry-form.js ticks Public or Private to match the plant picked in the dropdown
        'public_plant_ids': list(PlantJournal.objects.filter(
            planting__garden__owner=request.user, is_public=True,
        ).values_list('planting_id', flat=True)),
    }
    return render(request, 'journal/entry_form.html', context)


@login_required(login_url='/login')
def edit_entry(request, entry_id):
    if not is_grower(request.user):
        # The journal pages don't exist for buyers, they only see public plant pages
        raise Http404

    entry = get_object_or_404(JournalEntry, pk=entry_id)
    if entry.planting.garden.owner != request.user:
        raise PermissionDenied

    # Remember these before the form copies the new values onto the entry
    original_date = entry.date
    original_time = entry.time

    form = JournalEntryForm(request.user, request.POST or None, request.FILES or None, instance=entry)
    del form.fields['planting']

    if request.method == 'POST' and form.is_valid():
        # "photos" always counts as changed for a file field, so check new photos separately
        fields_changed = [name for name in form.changed_data if name != 'photos']
        new_photos = form.cleaned_data['photos'] or form.photo_urls()

        if not fields_changed and not new_photos:
            messages.info(request, 'No changes to save')
        else:
            form.save()
            delete_photos(form.cleaned_data['remove_photos'])
            save_new_photos(entry, form)
            messages.success(request, 'Changes saved')
        return redirect('journal:plant_detail', planting_id=entry.planting.pk)

    if PHOTO_ERROR in form.errors.get('photos', []):
        messages.error(request, "Couldn't upload your photo", extra_tags=PHOTO_ERROR)

    context = {
        'form': form,
        'entry': entry,
        'planting': entry.planting,
        'original_date': original_date,
        'original_time': original_time,
        'missing_required': has_missing_required(form),
        'nav_active': 'home',
    }
    return render(request, 'journal/entry_form.html', context)


# No login_required on the delete views: fetch would follow its redirect and get the login page,
# so anyone who isn't the owner (logged out or not) gets a JSON 403 the page can read instead
@require_POST
def delete_entry(request, entry_id):
    entry = get_object_or_404(JournalEntry, pk=entry_id)
    planting = entry.planting
    if planting.garden.owner != request.user:
        return JsonResponse({'message': 'You can only delete your own entries.'}, status=403)

    delete_photos(entry.photos.all())
    entry.delete()
    return JsonResponse({
        'message': 'Entry deleted',
        'plant_url': reverse('journal:plant_detail', args=[planting.pk]),
    })


@require_POST
def delete_plant_entries(request, planting_id):
    planting = get_object_or_404(Planting, pk=planting_id)
    if planting.garden.owner != request.user:
        return JsonResponse({'message': 'You can only delete your own entries.'}, status=403)

    # The plant itself stays, only its journal entries and their photos go
    delete_photos(EntryPhoto.objects.filter(entry__planting=planting))
    planting.journal_entries.all().delete()
    return JsonResponse({
        'message': 'Entries deleted',
        'detail': f"{planting.display_name}'s entries were removed. The plant stays in My gardens.",
    })


@require_POST
def toggle_visibility(request, planting_id):
    # The lock in the journal list: switches this plant's journal between private and public
    planting = get_object_or_404(Planting, pk=planting_id)
    if planting.garden.owner != request.user:
        return JsonResponse({'message': 'You can only change your own plants.'}, status=403)

    journal, _ = PlantJournal.objects.get_or_create(planting=planting)
    journal.is_public = not journal.is_public
    journal.save()

    if journal.is_public:
        message = f'{planting.display_name} is now public'
        detail = 'Other growers and buyers can see its journal.'
    else:
        message = f'{planting.display_name} is now private'
        detail = 'Only you can see its journal.'
    return JsonResponse({'is_public': journal.is_public, 'message': message, 'detail': detail})