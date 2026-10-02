from django.shortcuts import render


def show_main(request):
    context = {
        'app_name': 'urFunFarming',
    }
    return render(request, 'main.html', context)