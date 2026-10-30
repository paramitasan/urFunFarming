from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from care import planning
from care.forms import CareTaskFilterForm, CareTaskForm, WeatherPreferenceForm
from care.models import CareTask, WeatherPreference


def _wants_json(request):
    # Same handshake the marketplace module already uses, so the whole project
    # answers fetch requests the same way.
    return request.headers.get('X-Requested-With') == 'fetch' or request.headers.get('HX-Request') == 'true'


def _require_grower(request):
    """Plant care is a grower tool. Buyers get a short explanation instead of a form."""
    profile = getattr(request.user, 'profile', None)
    if not getattr(profile, 'is_grower', False):
        return render(request, 'care/grower_required.html', status=403)
    return None


def _own_task(request, pk):
    # Someone else's task answers 404, which does not even confirm that it exists.
    return get_object_or_404(
        CareTask.objects.select_related('planting__garden'), pk=pk, owner=request.user
    )


def _filtered_tasks(request, form):
    tasks = CareTask.objects.filter(owner=request.user).select_related('planting__garden')

    counts = tasks.aggregate(
        all=Count('id'),
        open=Count('id', filter=Q(is_done=False)),
        done=Count('id', filter=Q(is_done=True)),
        overdue=Count('id', filter=Q(is_done=False, planned_for__lt=timezone.localdate())),
    )

    show = form.cleaned_data.get('show', 'open')
    if show == 'open':
        tasks = tasks.filter(is_done=False)
    elif show == 'done':
        tasks = tasks.filter(is_done=True)
    elif show == 'overdue':
        tasks = tasks.filter(is_done=False, planned_for__lt=timezone.localdate())

    if form.cleaned_data.get('activity'):
        tasks = tasks.filter(activity=form.cleaned_data['activity'])
    if form.cleaned_data.get('planting'):
        tasks = tasks.filter(planting=form.cleaned_data['planting'])

    order = {
        'latest': ('-planned_for', '-planned_time', '-id'),
        'added': ('-created_at', '-id'),
    }.get(form.cleaned_data.get('sort'), ('planned_for', 'planned_time', 'id'))

    return tasks.order_by(*order), counts


def _list_context(request):
    # request.GET, never "or None": an unbound form has no cleaned_data at all,
    # and with empty data the clean_ methods supply the defaults.
    form = CareTaskFilterForm(request.GET, user=request.user)
    form.is_valid()
    tasks, counts = _filtered_tasks(request, form)

    preference = WeatherPreference.for_user(request.user)
    data = planning.load_forecast(preference)

    return {
        'tasks': tasks,
        'counts': counts,
        'filter_form': form,
        'preference': preference,
        'preference_form': WeatherPreferenceForm(instance=preference),
        'outlook': planning.today_outlook(data, preference),
        'today': timezone.localdate(),
        'nav_active': 'care',
    }


@login_required(login_url='/login')
@require_GET
def index(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied

    context = _list_context(request)
    # A fetch request only needs the part of the page that changed.
    if _wants_json(request):
        return JsonResponse({
            'status': 'success',
            'html': render_to_string('care/_task_list.html', context, request=request),
            'counts': context['counts'],
        })
    return render(request, 'care/index.html', context)


def _form_context(request, form, task=None):
    preference = WeatherPreference.for_user(request.user)
    data = planning.load_forecast(preference)
    planned_for = form['planned_for'].value()
    planned_time = form['planned_time'].value()
    if form.is_bound and form.is_valid():
        planned_for = form.cleaned_data['planned_for']
        planned_time = form.cleaned_data['planned_time']
    else:
        planned_for = form.fields['planned_for'].clean(planned_for) if planned_for else None
        planned_time = form.fields['planned_time'].clean(planned_time) if planned_time else None

    return {
        'form': form,
        'task': task,
        'preference': preference,
        'suggestions': planning.suggestions(data, preference),
        'verdict': planning.verdict(data, preference, planned_for, planned_time),
        'has_plantings': form.fields['planting'].queryset.exists(),
        'nav_active': 'care',
    }


def _save_task(request, task=None):
    """Shared by create and edit, because they differ only in the instance."""
    form = CareTaskForm(request.POST or None, instance=task, user=request.user)

    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        saved.owner = request.user
        saved.full_clean()
        saved.save()
        if _wants_json(request):
            return JsonResponse({'status': 'success', 'pk': saved.pk, 'redirect': '/care/'}, status=201 if task is None else 200)
        messages.success(request, 'Task saved.')
        return redirect('care:index')

    if request.method == 'POST' and _wants_json(request):
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)

    return render(
        request, 'care/form.html', _form_context(request, form, task),
        status=400 if request.method == 'POST' else 200,
    )


@login_required(login_url='/login')
@require_http_methods(['GET', 'POST'])
def create(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    return _save_task(request)


@login_required(login_url='/login')
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    return _save_task(request, _own_task(request, pk))


@login_required(login_url='/login')
@require_POST
def toggle_done(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    task = _own_task(request, pk)
    task.is_done = not task.is_done
    task.save(update_fields=['is_done', 'completed_at', 'updated_at'])

    if _wants_json(request):
        return JsonResponse({
            'status': 'success',
            'pk': task.pk,
            'is_done': task.is_done,
            'is_overdue': task.is_overdue,
        })
    messages.success(request, 'Task updated.')
    return redirect('care:index')


@login_required(login_url='/login')
@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    task = _own_task(request, pk)

    if request.method == 'POST':
        task.delete()
        if _wants_json(request):
            return JsonResponse({'status': 'success', 'pk': pk})
        messages.success(request, 'Task deleted.')
        return redirect('care:index')

    context = _list_context(request)
    context['delete_task'] = task
    return render(request, 'care/index.html', context)


@login_required(login_url='/login')
@require_POST
def update_preference(request):
    denied = _require_grower(request)
    if denied is not None:
        return denied
    preference = WeatherPreference.for_user(request.user)
    form = WeatherPreferenceForm(request.POST, instance=preference)

    if form.is_valid():
        form.save()
        if _wants_json(request):
            data = planning.load_forecast(preference)
            return JsonResponse({
                'status': 'success',
                'outlook': planning.today_outlook(data, preference),
            })
        messages.success(request, 'Weather limits saved.')
        return redirect('care:index')

    if _wants_json(request):
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)
    messages.error(request, 'Weather limits must be numbers inside the allowed range.')
    return redirect('care:index')


@login_required(login_url='/login')
@require_GET
def weather_check(request):
    """Judges one date and time. The form calls this while the grower is still choosing."""
    denied = _require_grower(request)
    if denied is not None:
        return denied

    form = CareTaskForm(user=request.user)
    try:
        planned_for = form.fields['planned_for'].clean(request.GET.get('date') or None)
    except Exception:
        planned_for = None
    try:
        planned_time = form.fields['planned_time'].clean(request.GET.get('time') or None)
    except Exception:
        planned_time = None

    preference = WeatherPreference.for_user(request.user)
    data = planning.load_forecast(preference)
    return JsonResponse({
        'status': 'success',
        'verdict': planning.verdict(data, preference, planned_for, planned_time),
    })
