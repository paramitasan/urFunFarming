from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from gardens.forms import GardenForm
from gardens.models import Garden


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


@never_cache
@require_GET
def my_gardens(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    gardens = Garden.objects.filter(owner=request.user).prefetch_related('plantings')
    return render(request, 'gardens/my_gardens.html', {'gardens': gardens})


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
    return render(request, 'gardens/detail.html', {'garden': garden})


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