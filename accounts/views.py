import datetime

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.forms import LoginForm, RegisterForm
from accounts.models import Profile


def register(request):
    # Signed-in users skip the form instead of seeing an empty one
    if request.user.is_authenticated:
        return redirect('main:show_main')

    form = RegisterForm()

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your account has been created. Log in to get started.')
            return redirect('accounts:login')

    context = {'form': form}
    return render(request, 'accounts/register.html', context)


def login_user(request):
    if request.user.is_authenticated:
        return redirect('main:show_main')

    if request.method == 'POST':
        form = LoginForm(data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Unchecked "Remember me" ends the session when the browser closes
            if not request.POST.get('remember_me'):
                request.session.set_expiry(0)
            response = HttpResponseRedirect(reverse('main:show_main'))
            response.set_cookie('last_login', str(datetime.datetime.now()))
            return response
    else:
        form = LoginForm(request)

    context = {'form': form}
    return render(request, 'accounts/login.html', context)


@login_required(login_url='/login')
def logout_user(request):
    logout(request)
    response = HttpResponseRedirect(reverse('accounts:login'))
    response.delete_cookie('last_login')
    return response


def form_errors(form):
    # {"field": ["message", ...]}, with "__all__" for errors that aren't on one field
    return {field: [str(error) for error in errors] for field, errors in form.errors.items()}


@require_POST
def register_ajax(request):
    form = RegisterForm(request.POST)

    if form.is_valid():
        form.save()
        messages.success(request, 'Your account has been created. Log in to get started.')
        return JsonResponse({'status': 'success', 'redirect': reverse('accounts:login')})

    return JsonResponse({'status': 'error', 'errors': form_errors(form)}, status=400)


@require_POST
def login_ajax(request):
    form = LoginForm(data=request.POST)

    if form.is_valid():
        user = form.get_user()
        login(request, user)
        if not request.POST.get('remember_me'):
            request.session.set_expiry(0)
        response = JsonResponse({'status': 'success', 'redirect': reverse('main:show_main')})
        response.set_cookie('last_login', str(datetime.datetime.now()))
        return response

    return JsonResponse({'status': 'error', 'errors': form_errors(form)}, status=400)


def me_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({'is_authenticated': False})

    profile = Profile.objects.filter(user=request.user).first()
    data = {
        'is_authenticated': True,
        'username': request.user.username,
        'display_name': profile.display_name if profile else request.user.username,
        'is_grower': profile.is_grower if profile else False,
        'is_buyer': profile.is_buyer if profile else False,
        'last_login': request.COOKIES.get('last_login', 'Never'),
    }
    return JsonResponse(data)


def profile_json(request, username):
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=user)
    data = {
        'username': user.username,
        'display_name': profile.display_name,
        'is_grower': profile.is_grower,
        'is_buyer': profile.is_buyer,
        'created_at': profile.created_at.isoformat(),
    }
    return JsonResponse(data)
