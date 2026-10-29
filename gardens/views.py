from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce, Lower, NullIf
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from gardens.forms import (
    GardenExploreFilterForm,
    GardenForm,
    GardenListFilterForm,
    PlantingFilterForm,
    PlantingForm,
)
from gardens.models import Garden, Planting


def _require_grower(request):
    # Only creating needs the grower role; owners keep access to what they already made
    if not getattr(getattr(request.user, 'profile', None), 'is_grower', False):
        return render(request, 'gardens/grower_required.html', {'nav_active': 'home'}, status=403)
    return None


def _owned_garden(request, pk):
    return get_object_or_404(Garden, pk=pk, owner=request.user)


def _owned_planting(request, garden_pk, planting_pk):
    return get_object_or_404(
        Planting.objects.select_related('garden'),
        pk=planting_pk,
        garden_id=garden_pk,
        garden__owner=request.user,
    )


def _public_gardens():
    return Garden.objects.filter(is_public=True, owner__is_active=True)


def _search_gardens(gardens, query):
    # A subquery keeps the plantings join out of the outer query, so planting_count stays the full count
    matching = Garden.objects.filter(
        Q(name__icontains=query)
        | Q(location__icontains=query)
        | Q(growing_method__icontains=query)
        | Q(public_summary__icontains=query)
        | Q(plantings__name__icontains=query)
        | Q(plantings__crop__icontains=query)
    ).values('pk')
    return gardens.filter(pk__in=matching)


def _filtered_plantings(garden, params):
    form = PlantingFilterForm(params)
    # Same fallbacks as Planting.display_name and Planting.method
    plantings = garden.plantings.annotate(
        method_name=Coalesce(NullIf('growing_method', Value('')), Value(garden.growing_method)),
        sort_name=Coalesce(NullIf('name', Value('')), 'crop'),
    )
    methods = list(plantings.order_by('method_name').values_list('method_name', flat=True).distinct())
    if form.is_valid():
        query = form.cleaned_data['q']
        month = form.cleaned_data['month']
        method = form.cleaned_data['method']
        if query:
            plantings = plantings.filter(Q(name__icontains=query) | Q(crop__icontains=query))
        if month:
            plantings = plantings.filter(planting_date__month=month)
        if method:
            plantings = plantings.filter(method_name=method)
        sort = form.cleaned_data['sort']
        order = {
            'oldest': ('planting_date', Lower('sort_name'), 'id'),
            'name': (Lower('sort_name'), 'id'),
        }.get(sort, ('-planting_date', Lower('sort_name'), 'id'))
        plantings = plantings.order_by(*order)
    else:
        plantings = plantings.none()
    return form, plantings, plantings.count(), methods


@never_cache
@require_GET
def explore(request):
    form = GardenExploreFilterForm(request.GET)
    gardens = _public_gardens()
    if request.user.is_authenticated:
        gardens = gardens.exclude(owner=request.user)
    methods = list(gardens.order_by('growing_method').values_list('growing_method', flat=True).distinct())
    locations = list(gardens.order_by('location').values_list('location', flat=True).distinct())
    if form.is_valid():
        query = form.cleaned_data['q']
        location = form.cleaned_data['location']
        method = form.cleaned_data['method']
        if query:
            gardens = _search_gardens(gardens, query)
        if location:
            gardens = gardens.filter(location=location)
        if method:
            gardens = gardens.filter(growing_method=method)
    else:
        gardens = gardens.none()
    gardens = gardens.annotate(planting_count=Count('plantings', distinct=True))
    garden_count = gardens.count()
    sort = form.cleaned_data['sort'] if form.is_valid() else 'newest'
    order = {'oldest': ('created_at', 'id'), 'name': (Lower('name'), 'id')}.get(sort, ('-created_at', '-id'))
    gardens = gardens.order_by(*order).values(
        'id', 'name', 'location', 'growing_method', 'public_summary', 'planting_count', 'created_at',
        'owner__username', 'owner__date_joined', 'owner__profile__display_name',
    )
    return render(
        request,
        'gardens/explore.html',
        {
            'filter_form': form,
            'gardens': gardens,
            'nav_active': 'explore',
            'garden_count': garden_count,
            'methods': methods,
            'locations': locations,
            'has_gardens': bool(locations),
        },
    )


@never_cache
@require_GET
def public_detail(request, pk):
    # Explore never lists your own gardens, so the owner always gets their own view, public or private
    if request.user.is_authenticated and Garden.objects.filter(pk=pk, owner=request.user).exists():
        return redirect('gardens:detail', pk=pk)
    garden = get_object_or_404(
        _public_gardens().annotate(total_plantings=Count('plantings')).values(
            'id', 'name', 'location', 'growing_method', 'public_summary', 'total_plantings',
            'owner__username', 'owner__profile__display_name', 'owner__profile__area',
        ),
        pk=pk,
    )
    garden_instance = Garden.objects.get(pk=garden['id'])
    filter_form, plantings, planting_count, methods = _filtered_plantings(garden_instance, request.GET)
    return render(
        request,
        'gardens/public_detail.html',
        {
            'garden': garden,
            'plantings': plantings,
            'filter_form': filter_form,
            'planting_count': planting_count,
            'has_plants': bool(methods),
            'nav_active': 'explore',
        },
    )


@login_required(login_url='/login')
@never_cache
@require_GET
def my_gardens(request):
    form = GardenListFilterForm(request.GET)
    gardens = Garden.objects.filter(owner=request.user)
    locations = list(gardens.order_by('location').values_list('location', flat=True).distinct())
    visibility_counts = {'': 0, 'public': 0, 'private': 0}
    if form.is_valid():
        query = form.cleaned_data['q']
        location = form.cleaned_data['location']
        visibility = form.cleaned_data['visibility']
        if query:
            gardens = _search_gardens(gardens, query)
        if location:
            gardens = gardens.filter(location=location)
        # Counts next to each Visibility option, before that filter is applied
        totals = gardens.aggregate(
            total=Count('id', distinct=True),
            public=Count('id', distinct=True, filter=Q(is_public=True)),
            private=Count('id', distinct=True, filter=Q(is_public=False)),
        )
        visibility_counts = {'': totals['total'], 'public': totals['public'], 'private': totals['private']}
        if visibility == 'public':
            gardens = gardens.filter(is_public=True)
        elif visibility == 'private':
            gardens = gardens.filter(is_public=False)
        order = {
            'oldest': ('created_at', 'id'),
            'name': (Lower('name'), 'id'),
        }.get(form.cleaned_data['sort'], ('-created_at', '-id'))
        gardens = gardens.order_by(*order)
    else:
        gardens = gardens.none()
    gardens = gardens.annotate(planting_count=Count('plantings', distinct=True))
    visibility_options = [
        (value, label, visibility_counts[value]) for value, label in form.fields['visibility'].choices
    ]
    return render(
        request,
        'gardens/my_gardens.html',
        {
            'gardens': gardens,
            'garden_count': gardens.count(),
            'filter_form': form,
            'locations': locations,
            'visibility_options': visibility_options,
            'has_gardens': bool(locations),
            'nav_active': 'home',
        },
    )


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def create(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    form = GardenForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        garden = form.save(commit=False)
        garden.owner = request.user
        garden.save()
        messages.success(request, 'Garden created.')
        return redirect('gardens:detail', pk=garden.pk)
    return render(
        request,
        'gardens/form.html',
        {'form': form, 'nav_active': 'home'},
        status=400 if request.method == 'POST' else 200,
    )


@login_required(login_url='/login')
@never_cache
@require_GET
def detail(request, pk):
    garden = _owned_garden(request, pk)
    filter_form, plantings, planting_count, methods = _filtered_plantings(garden, request.GET)
    return render(
        request,
        'gardens/detail.html',
        {
            'garden': garden,
            'plantings': plantings,
            'planting_count': planting_count,
            'methods': methods,
            'has_plants': bool(methods),
            'filter_form': filter_form,
            'nav_active': 'home',
        },
    )


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    garden = _owned_garden(request, pk)
    form = GardenForm(request.POST if request.method == 'POST' else None, instance=garden)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Garden updated.')
        return redirect('gardens:detail', pk=garden.pk)
    return render(
        request,
        'gardens/form.html',
        {'form': form, 'garden': garden, 'nav_active': 'home'},
        status=400 if request.method == 'POST' else 200,
    )


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    garden = _owned_garden(request, pk)
    if request.method == 'POST':
        garden.delete()
        messages.success(request, 'Garden deleted.')
        return redirect('gardens:mine')
    return render(request, 'gardens/delete.html', {'garden': garden, 'nav_active': 'home'})


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def planting_create(request, garden_pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    garden = _owned_garden(request, garden_pk)
    form = PlantingForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        planting = form.save(commit=False)
        planting.garden = garden
        planting.save()
        messages.success(request, 'Planting added.')
        return redirect('gardens:planting_detail', garden_pk=garden.pk, planting_pk=planting.pk)
    return render(
        request,
        'gardens/planting_form.html',
        {'form': form, 'garden': garden, 'nav_active': 'home'},
        status=400 if request.method == 'POST' else 200,
    )


@never_cache
@require_GET
def planting_detail(request, garden_pk, planting_pk):
    # Shared plant page: the owner always sees it, everyone sees plants of a public garden,
    # and anyone else gets the "No access" state without any of the plant's details
    planting = get_object_or_404(
        Planting.objects.select_related('garden__owner'),
        pk=planting_pk,
        garden_id=garden_pk,
    )
    garden = planting.garden
    is_owner = garden.owner_id == request.user.pk
    if not is_owner and not (garden.is_public and garden.owner.is_active):
        return render(
            request,
            'gardens/planting_detail.html',
            {'no_access': True, 'nav_active': 'explore'},
            status=403,
        )
    return render(
        request,
        'gardens/planting_detail.html',
        {
            'garden': garden,
            'planting': planting,
            'is_owner': is_owner,
            'nav_active': 'home' if is_owner else 'explore',
        },
    )


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def planting_edit(request, garden_pk, planting_pk):
    planting = _owned_planting(request, garden_pk, planting_pk)
    form = PlantingForm(request.POST if request.method == 'POST' else None, instance=planting)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Planting updated.')
        return redirect('gardens:planting_detail', garden_pk=garden_pk, planting_pk=planting.pk)
    return render(
        request,
        'gardens/planting_form.html',
        {'form': form, 'garden': planting.garden, 'planting': planting, 'nav_active': 'home'},
        status=400 if request.method == 'POST' else 200,
    )


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def planting_delete(request, garden_pk, planting_pk):
    planting = _owned_planting(request, garden_pk, planting_pk)
    if request.method == 'POST':
        planting.delete()
        messages.success(request, 'Planting deleted.')
        return redirect('gardens:detail', pk=garden_pk)
    return render(
        request,
        'gardens/planting_delete.html',
        {'garden': planting.garden, 'planting': planting, 'nav_active': 'home'},
    )
