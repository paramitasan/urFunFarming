from django.shortcuts import render

from accounts.models import Profile


# Sample listings until the market app is ready
LISTINGS = [
    {'title': 'Butterhead lettuce, 2 heads', 'grower': 'Ayu, Tebet', 'price': 'Rp9.000', 'until': 'Until Sat', 'category': 'leafy'},
    {'title': 'Cherry tomatoes, 500 g', 'grower': 'Rina, Rawamangun', 'price': 'Rp15.000', 'until': 'Until Fri', 'category': 'fruiting'},
    {'title': 'Carrots, 1 kg', 'grower': 'Bayu, Cikini', 'price': 'Rp12.000', 'until': 'Until Sun', 'category': 'root'},
    {'title': 'Thai basil, 3 bunches', 'grower': 'Sekar, Kemang', 'price': 'Free', 'until': 'Today only', 'category': 'herbs'},
    {'title': 'Kangkung, 4 bunches', 'grower': 'Rina, Tebet', 'price': 'Rp8.000', 'until': 'Until Thu', 'category': 'leafy'},
    {'title': 'Mint, 2 bunches', 'grower': 'Yoga, Bintaro', 'price': 'Free', 'until': 'Until Wed', 'category': 'herbs'},
    {'title': 'Bird’s eye chili, 250 g', 'grower': 'Dimas, Kemang', 'price': 'Rp9.000', 'until': 'Until Sun', 'category': 'fruiting'},
    {'title': 'Roma tomatoes, 1 kg', 'grower': 'Maria, Cempaka Putih', 'price': 'Rp22.000', 'until': 'Until Mon', 'category': 'fruiting'},
]

CATEGORIES = [
    ('all', 'All'),
    ('leafy', 'Leafy greens'),
    ('herbs', 'Herbs'),
    ('fruiting', 'Fruiting veg'),
    ('free', 'Free to collect'),
]


def get_listings(category):
    if category == 'free':
        return [item for item in LISTINGS if item['price'] == 'Free']
    if category in ('leafy', 'herbs', 'fruiting'):
        return [item for item in LISTINGS if item['category'] == category]
    return LISTINGS


def show_main(request):
    profile = None
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()

    context = {
        'app_name': 'urFunFarming',
        'listings': LISTINGS,
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
