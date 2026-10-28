from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db.models import Count, Q
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
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    if not getattr(getattr(request.user, 'profile', None), 'is_grower', False):
        return render(request, 'gardens/grower_required.html', status=403)
    return None


def _owned_garden(request, pk):
    return get_object_or_404(
        Garden.objects.prefetch_related('plantings'),
        pk=pk,
        owner=request.user,
    )


def _owned_planting(request, garden_pk, planting_pk):
    return get_object_or_404(
        Planting.objects.select_related('garden'),
        pk=planting_pk,
        garden_id=garden_pk,
        garden__owner=request.user,
    )


def _public_gardens():
    return Garden.objects.filter(is_public=True, owner__is_active=True)


def _filtered_plantings(garden, params):
    form = PlantingFilterForm(params)
    plantings = garden.plantings.all()
    if form.is_valid():
        query = form.cleaned_data['q']
        month = form.cleaned_data['month']
        method = form.cleaned_data['method']
        if query:
            plantings = plantings.filter(crop__icontains=query)
        if month:
            plantings = plantings.filter(planting_date__month=month)
        if method and method != garden.growing_method:
            plantings = plantings.none()
        sort = form.cleaned_data['sort']
        order = {'oldest': ('planting_date', 'crop', 'id'), 'name': ('crop', 'id')}.get(
            sort,
            ('-planting_date', 'crop', 'id'),
        )
        plantings = plantings.order_by(*order)
    else:
        plantings = plantings.none()
    return form, plantings, plantings.count()


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
            gardens = gardens.filter(
                Q(name__icontains=query)
                | Q(location__icontains=query)
                | Q(growing_method__icontains=query)
                | Q(public_summary__icontains=query)
                | Q(plantings__crop__icontains=query)
            ).distinct()
        if location:
            gardens = gardens.filter(location=location)
        if method:
            gardens = gardens.filter(growing_method=method)
    else:
        gardens = gardens.none()
    gardens = gardens.annotate(planting_count=Count('plantings', distinct=True))
    garden_count = gardens.count()
    sort = form.cleaned_data['sort'] if form.is_valid() else 'newest'
    order = {'oldest': ('created_at', 'id'), 'name': ('name', 'id')}.get(sort, ('-created_at', '-id'))
    gardens = gardens.order_by(*order).values(
        'id', 'name', 'location', 'growing_method', 'public_summary', 'planting_count', 'created_at',
        'owner__username', 'owner__profile__display_name',
    )
    return render(
        request,
        'gardens/explore.html',
        {
            'filter_form': form,
            'gardens': gardens,
            'garden_count': garden_count,
            'methods': methods,
            'locations': locations,
        },
    )


@never_cache
@require_GET
def public_detail(request, pk):
    garden = get_object_or_404(
        _public_gardens().values(
            'id', 'name', 'location', 'growing_method', 'public_summary',
            'owner__username', 'owner__profile__display_name',
        ),
        pk=pk,
    )
    garden_instance = Garden.objects.get(pk=garden['id'])
    filter_form, plantings, planting_count = _filtered_plantings(garden_instance, request.GET)
    return render(
        request,
        'gardens/public_detail.html',
        {
            'garden': garden,
            'plantings': plantings.values('crop', 'planting_date'),
            'filter_form': filter_form,
            'planting_count': planting_count,
        },
    )


@never_cache
@require_GET
def my_gardens(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    form = GardenListFilterForm(request.GET)
    gardens = Garden.objects.filter(owner=request.user)
    locations = list(gardens.order_by('location').values_list('location', flat=True).distinct())
    if form.is_valid():
        query = form.cleaned_data['q']
        location = form.cleaned_data['location']
        visibility = form.cleaned_data['visibility']
        if query:
            gardens = gardens.filter(
                Q(name__icontains=query)
                | Q(location__icontains=query)
                | Q(growing_method__icontains=query)
                | Q(public_summary__icontains=query)
                | Q(plantings__crop__icontains=query)
            ).distinct()
        if location:
            gardens = gardens.filter(location=location)
        if visibility == 'public':
            gardens = gardens.filter(is_public=True)
        elif visibility == 'private':
            gardens = gardens.filter(is_public=False)
        order = {
            'oldest': ('created_at', 'id'),
            'name': ('name', 'id'),
        }.get(form.cleaned_data['sort'], ('-created_at', '-id'))
        gardens = gardens.order_by(*order)
    else:
        gardens = gardens.none()
    gardens = gardens.annotate(planting_count=Count('plantings', distinct=True)).prefetch_related('plantings')
    return render(
        request,
        'gardens/my_gardens.html',
        {'gardens': gardens, 'garden_count': gardens.count(), 'filter_form': form, 'locations': locations},
    )


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
    return render(request, 'gardens/form.html', {'form': form}, status=400 if request.method == 'POST' else 200)


@never_cache
@require_GET
def detail(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    garden = _owned_garden(request, pk)
    filter_form, plantings, planting_count = _filtered_plantings(garden, request.GET)
    return render(
        request,
        'gardens/detail.html',
        {
            'garden': garden,
            'plantings': plantings,
            'planting_count': planting_count,
            'filter_form': filter_form,
        },
    )


@never_cache
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    garden = _owned_garden(request, pk)
    form = GardenForm(request.POST if request.method == 'POST' else None, instance=garden)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Garden updated.')
        return redirect('gardens:detail', pk=garden.pk)
    return render(
        request,
        'gardens/form.html',
        {'form': form, 'garden': garden},
        status=400 if request.method == 'POST' else 200,
    )


@never_cache
@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    garden = _owned_garden(request, pk)
    if request.method == 'POST':
        garden.delete()
        messages.success(request, 'Garden deleted.')
        return redirect('gardens:mine')
    return render(request, 'gardens/delete.html', {'garden': garden})


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
        {'form': form, 'garden': garden},
        status=400 if request.method == 'POST' else 200,
    )


@never_cache
@require_GET
def planting_detail(request, garden_pk, planting_pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    planting = _owned_planting(request, garden_pk, planting_pk)
    return render(request, 'gardens/planting_detail.html', {'garden': planting.garden, 'planting': planting})


@never_cache
@require_http_methods(['GET', 'POST'])
def planting_edit(request, garden_pk, planting_pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    planting = _owned_planting(request, garden_pk, planting_pk)
    form = PlantingForm(request.POST if request.method == 'POST' else None, instance=planting)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Planting updated.')
        return redirect('gardens:planting_detail', garden_pk=garden_pk, planting_pk=planting.pk)
    return render(
        request,
        'gardens/planting_form.html',
        {'form': form, 'garden': planting.garden, 'planting': planting},
        status=400 if request.method == 'POST' else 200,
    )


@never_cache
@require_http_methods(['GET', 'POST'])
def planting_delete(request, garden_pk, planting_pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    planting = _owned_planting(request, garden_pk, planting_pk)
    if request.method == 'POST':
        planting.delete()
        messages.success(request, 'Planting deleted.')
        return redirect('gardens:detail', pk=garden_pk)
    return render(request, 'gardens/planting_delete.html', {'garden': planting.garden, 'planting': planting})