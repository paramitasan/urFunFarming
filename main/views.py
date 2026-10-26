import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

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
    if request.user.is_authenticated:
        return redirect('main:home')

    context = {
        'period': get_period(timezone.localtime().hour),
        'app_name': 'urFunFarming',
        'listings': get_listings('all'),
        'listing_count': HarvestListing.objects.available_now().count(),
        'categories': CATEGORIES,
        'active': 'all',
    }
    return render(request, 'landing.html', context)


def get_period(hour):
    if hour < 11:
        return 'morning'
    if hour < 15:
        return 'afternoon'
    if hour < 19:
        return 'evening'
    return 'night'


def parse_last_login(value):
    # The cookie holds str(datetime.now()) in the server's time zone (Asia/Jakarta)
    try:
        return datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@login_required(login_url='/login')
def home(request):
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'display_name': request.user.username})
    now = timezone.localtime()

    if profile.is_grower and profile.is_buyer:
        roles = 'Grower and buyer'
    elif profile.is_grower:
        roles = 'Grower'
    elif profile.is_buyer:
        roles = 'Buyer'
    else:
        roles = ''
    place = ', '.join(part for part in (profile.area, profile.city) if part)

    # Live count for the Market tile, the same listings the landing page shows
    listing_count = HarvestListing.objects.available_now().count()
    if listing_count:
        market_text = f'{listing_count} harvest{"" if listing_count == 1 else "s"} near you right now. Arrange a pickup.'
    else:
        market_text = 'Browse harvests near you and arrange a pickup.'

    period = get_period(now.hour)
    context = {
        'market_text': market_text,
        'profile': profile,
        'period': period,
        'greeting': f'Good {period}',
        'today': now,
        'last_login': parse_last_login(request.COOKIES.get('last_login')),
        'details': ' · '.join(part for part in (roles, place) if part),
    }
    return render(request, 'home.html', context)


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
