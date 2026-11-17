import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.forms import DeleteAccountForm, LoginForm, PasswordForm, ProfileForm, RegisterForm
from accounts.models import Profile
from forum.models import Forum
from gardens.models import Garden, Planting
from journal.models import EntryPhoto


def register(request):
    # Signed-in users skip the form instead of seeing an empty one
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    form = RegisterForm()

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your account has been created. Log in to get started.')
            return redirect('accounts:login')

    context = {'form': form}
    return render(request, 'accounts/register.html', context)


def _login_target(request):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return settings.LOGIN_REDIRECT_URL


def login_user(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == 'POST':
        form = LoginForm(data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Unchecked "Remember me" ends the session when the browser closes
            if not request.POST.get('remember_me'):
                request.session.set_expiry(0)
            response = HttpResponseRedirect(_login_target(request))
            response.set_cookie('last_login', str(datetime.datetime.now()))
            return response
    else:
        form = LoginForm(request)

    context = {'form': form}
    return render(request, 'accounts/login.html', context)


@login_required(login_url='/login')
@require_POST
def logout_user(request):
    logout(request)
    response = HttpResponseRedirect(reverse('accounts:login'))
    response.delete_cookie('last_login')
    return response


def form_errors(form):
    # Errors not tied to one field come under "__all__"
    return {field: [str(error) for error in errors] for field, errors in form.errors.items()}


@require_POST
def register_ajax(request):
    if request.user.is_authenticated:
        return JsonResponse({'status': 'success', 'redirect': settings.LOGIN_REDIRECT_URL})

    form = RegisterForm(request.POST)

    if form.is_valid():
        form.save()
        messages.success(request, 'Your account has been created. Log in to get started.')
        return JsonResponse({'status': 'success', 'redirect': reverse('accounts:login')})

    return JsonResponse({'status': 'error', 'errors': form_errors(form)}, status=400)


@require_POST
def login_ajax(request):
    if request.user.is_authenticated:
        return JsonResponse({'status': 'success', 'redirect': settings.LOGIN_REDIRECT_URL})

    form = LoginForm(data=request.POST)

    if form.is_valid():
        user = form.get_user()
        login(request, user)
        if not request.POST.get('remember_me'):
            request.session.set_expiry(0)
        response = JsonResponse({'status': 'success', 'redirect': _login_target(request)})
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
        'bio': profile.bio,
        'area': profile.area,
        'city': profile.city,
        'created_at': profile.created_at.isoformat(),
    }
    # Contact details are for signed-in members only
    if request.user.is_authenticated:
        data['phone'] = profile.phone
        data['contact_email'] = profile.contact_email
    return JsonResponse(data)


def profile_summary(profile):
    return {
        'display_name': profile.display_name,
        'initials': profile.initials,
        'is_grower': profile.is_grower,
        'is_buyer': profile.is_buyer,
        'area': profile.area,
        'city': profile.city,
    }


@login_required(login_url='/login')
def profile(request):
    # Always the signed-in user's own profile, whatever the form sends
    user_profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'display_name': request.user.username})
    profile_form = ProfileForm(instance=user_profile)
    password_form = PasswordForm(request.user)
    is_fetch = request.headers.get('X-Requested-With') == 'fetch'

    if request.method == 'POST' and 'save_profile' in request.POST:
        profile_form = ProfileForm(request.POST, instance=user_profile)
        if profile_form.is_valid():
            profile_form.save()
            message = 'Profile saved. Neighbors will see the changes right away.'
            if is_fetch:
                return JsonResponse({'status': 'success', 'message': message, 'profile': profile_summary(user_profile)})
            messages.success(request, message)
            return redirect('accounts:profile')
        if is_fetch:
            return JsonResponse({'status': 'error', 'errors': form_errors(profile_form)}, status=400)

    elif request.method == 'POST' and 'change_password' in request.POST:
        password_form = PasswordForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            # Keeps this session valid after the password hash changes
            update_session_auth_hash(request, user)
            message = 'Password updated. You are still logged in on this device.'
            if is_fetch:
                return JsonResponse({'status': 'success', 'message': message})
            messages.success(request, message)
            return redirect('accounts:profile')
        if is_fetch:
            return JsonResponse({'status': 'error', 'errors': form_errors(password_form)}, status=400)

    context = {
        'profile': user_profile,
        'profile_form': profile_form,
        'password_form': password_form,
        'delete_form': DeleteAccountForm(request.user),
    }
    return render(request, 'accounts/profile.html', context)


@login_required(login_url='/login')
@require_POST
def delete_account(request):
    # Always deletes request.user; the form carries only the password, never a user id
    form = DeleteAccountForm(request.user, request.POST)
    is_fetch = request.headers.get('X-Requested-With') == 'fetch'

    if not form.is_valid():
        if is_fetch:
            return JsonResponse({'status': 'error', 'errors': form_errors(form)}, status=400)
        # Without JavaScript: show the profile page again with the error under the password
        user_profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'display_name': request.user.username})
        context = {
            'profile': user_profile,
            'profile_form': ProfileForm(instance=user_profile),
            'password_form': PasswordForm(request.user),
            'delete_form': form,
        }
        return render(request, 'accounts/profile.html', context, status=400)

    user = request.user
    file_names = uploaded_file_names(user)
    with transaction.atomic():
        user.delete()
        # Only once the delete is committed; a rollback would otherwise leave rows pointing at missing files
        transaction.on_commit(lambda: delete_uploaded_files(file_names))

    # Ends this session and rotates the session key, like the logout view
    logout(request)
    message = 'Your account was deleted. Thanks for growing with us.'
    # The login page is the first one that shows messages, so the goodbye is seen right away
    if is_fetch:
        response = JsonResponse({'status': 'success', 'message': message, 'redirect': reverse('accounts:login')})
    else:
        messages.success(request, message)
        response = HttpResponseRedirect(reverse('accounts:login'))
    response.delete_cookie('last_login')
    return response


def uploaded_file_names(user):
    # Every file this user uploaded, in all apps, so none is left behind in media/
    names = []
    for queryset, field in (
        (Garden.objects.filter(owner=user), 'photo'),
        (Planting.objects.filter(garden__owner=user), 'photo'),
        (EntryPhoto.objects.filter(entry__planting__garden__owner=user), 'image'),
        (Forum.objects.filter(author=user), 'image'),
    ):
        names.extend(queryset.exclude(**{field: ''}).exclude(**{f'{field}__isnull': True}).values_list(field, flat=True))
    return names


def delete_uploaded_files(names):
    for name in names:
        # Mirrors journal's delete_photos: missing files are ignored, never an error for the user
        if default_storage.exists(name):
            default_storage.delete(name)
