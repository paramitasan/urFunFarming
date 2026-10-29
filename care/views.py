from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce, Lower, NullIf
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from care.forms import CareSettingsForm, CareTaskForm, StatusForm, TaskFilterForm
from care.models import CareSettings, CareTask
from care.planning import best_times, today_card
from weather.services import forecast_for_user


def _require_grower(request):
    # Plant care is a grower tool; buyer-only accounts get the "add the grower role" page
    if not getattr(getattr(request.user, 'profile', None), 'is_grower', False):
        return render(request, 'care/grower_required.html', {'nav_active': 'home'}, status=403)
    return None


def _owned_task(request, pk):
    # Someone else's task is a 404, never a peek at it
    return get_object_or_404(CareTask.objects.select_related('planting__garden'), pk=pk, owner=request.user)


def _back_to_list(request):
    # Keeps the chosen filter and sort after a status change, but only for our own site
    target = request.POST.get('next', '')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect('care:index')


def _form_context(request, form, task=None):
    care_settings = CareSettings.for_user(request.user)
    weather = forecast_for_user(request.user)
    return {
        'form': form,
        'task': task,
        'settings_form': CareSettingsForm(instance=care_settings),
        'care_settings': care_settings,
        'weather': weather,
        'best_times': best_times(weather, care_settings),
        'has_plantings': form.fields['planting'].queryset.exists(),
        'nav_active': 'home',
    }


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET'])
def index(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    form = TaskFilterForm(request.GET)
    form.is_valid()
    status = form.cleaned_data.get('status') or 'todo'
    sort = form.cleaned_data.get('sort') or 'soonest'

    tasks = CareTask.objects.filter(owner=request.user)
    totals = tasks.aggregate(
        all=Count('id'),
        todo=Count('id', filter=Q(status=CareTask.Status.TODO)),
        in_progress=Count('id', filter=Q(status=CareTask.Status.IN_PROGRESS)),
        completed=Count('id', filter=Q(status=CareTask.Status.COMPLETED)),
    )
    if status != 'all':
        tasks = tasks.filter(status=status)
    order = {
        'latest': ('-target_date', '-target_time', '-id'),
        'plant': (Lower(Coalesce(NullIf('planting__name', Value('')), 'planting__crop')), 'target_date', 'id'),
        'newest': ('-created_at', '-id'),
    }.get(sort, ('target_date', 'target_time', 'id'))
    tasks = tasks.select_related('planting__garden').order_by(*order)

    care_settings = CareSettings.for_user(request.user)
    weather = forecast_for_user(request.user)
    status_filters = [
        (value, label, totals[value]) for value, label in form.fields['status'].choices
    ]
    return render(request, 'care/index.html', {
        'tasks': tasks,
        'status': status,
        'sort': sort,
        'filter_form': form,
        'status_filters': status_filters,
        'total_tasks': totals['all'],
        'status_choices': CareTask.Status.choices,
        'care_settings': care_settings,
        'weather': weather,
        'card': today_card(weather, care_settings),
        'settings_form': CareSettingsForm(instance=care_settings),
        'today': timezone.localdate(),
        'nav_active': 'home',
    })


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def create(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    form = CareTaskForm(request.POST if request.method == 'POST' else None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.save()
        messages.success(request, 'Task added.')
        return redirect('care:index')
    return render(
        request, 'care/form.html', _form_context(request, form),
        status=400 if request.method == 'POST' else 200,
    )


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    task = _owned_task(request, pk)
    form = CareTaskForm(request.POST if request.method == 'POST' else None, instance=task, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Task updated.')
        return redirect('care:index')
    return render(
        request, 'care/form.html', _form_context(request, form, task),
        status=400 if request.method == 'POST' else 200,
    )


@login_required(login_url='/login')
@never_cache
@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    task = _owned_task(request, pk)
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Task deleted.')
        return redirect('care:index')
    return render(request, 'care/delete.html', {'task': task, 'nav_active': 'home'})


@login_required(login_url='/login')
@require_POST
def change_status(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    task = _owned_task(request, pk)
    form = StatusForm(request.POST)
    if form.is_valid():
        task.status = form.cleaned_data['status']
        task.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Marked "{task.title}" as {task.get_status_display()}.')
    else:
        messages.error(request, 'Choose a valid status.')
    return _back_to_list(request)


@login_required(login_url='/login')
@require_POST
def update_settings(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    form = CareSettingsForm(request.POST, instance=CareSettings.for_user(request.user))
    if form.is_valid():
        form.save()
        messages.success(request, 'Thresholds saved.')
    else:
        messages.error(request, 'Thresholds must be numbers of 0 or more.')
    return _back_to_list(request)
