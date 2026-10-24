from django.shortcuts import render

from accounts.models import Profile
from marketplace.models import HarvestListing


CATEGORIES = [
    ('all', 'All'),
    ('vegetables', 'Vegetables'),
    ('fruits', 'Fruits'),
    ('herbs', 'Herbs'),
    ('free', 'Free to collect'),
]


def get_listings(category):
    queryset = HarvestListing.objects.available_now().select_related('owner', 'owner__profile')
    if category == 'free':
        queryset = queryset.filter(price=0)
    elif category in HarvestListing.Category.values:
        queryset = queryset.filter(category=category)
    return queryset[:8]


def show_main(request):
    profile = None
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()

    context = {
        'app_name': 'urFunFarming',
        'listings': get_listings('all'),
        'listing_count': HarvestListing.objects.available_now().count(),
        'categories': CATEGORIES,
        'active': 'all',
        'profile': profile,
        'last_login': request.COOKIES.get('last_login', 'Never'),
    }
    return render(request, 'landing.html', context)


def filter_listings(request):
    active = request.GET.get('category', 'all')
    if active not in dict(CATEGORIES):
        active = 'all'
    context = {
        'listings': get_listings(active),
        'categories': CATEGORIES,
        'active': active,
    }
    return render(request, 'partials/listing_filter.html', context)
