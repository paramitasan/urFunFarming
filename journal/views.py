from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='/login')
def index(request):
    context = {}
    return render(request, 'journal/index.html', context)