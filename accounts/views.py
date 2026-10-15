import datetime

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.forms import LoginForm, RegisterForm


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
