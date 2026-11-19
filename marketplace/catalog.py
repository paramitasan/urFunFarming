"""List queries shared by the website and the mobile API."""
from django.core.paginator import Paginator
from django.db.models import Q

from marketplace.forms import ListingFilterForm
from marketplace.models import HarvestListing


def listings():
    return HarvestListing.objects.select_related('owner', 'owner__profile')


def catalog_page(params, user, *, mine=False):
    params = params.copy()
    params.setdefault('availability', 'any' if mine else 'now')
    params.setdefault('sort', 'newest')
    form = ListingFilterForm(params)
    queryset = listings().filter(owner=user) if mine else listings().public()
    if form.is_valid():
        values = form.cleaned_data
        if values['q']:
            text = values['q']
            queryset = queryset.filter(Q(title__icontains=text) | Q(description__icontains=text) | Q(area__icontains=text) | Q(owner__profile__display_name__icontains=text))
        for field in ('category', 'city', 'area'):
            if values[field]:
                queryset = queryset.filter(**{field: values[field]})
        if values['grower']:
            queryset = queryset.filter(owner__username=values['grower'])
        if values['availability'] == 'now':
            queryset = queryset.available_now()
        if values['price_type'] == 'free':
            queryset = queryset.filter(price=0)
        elif values['price_type'] == 'paid':
            queryset = queryset.filter(price__gt=0)
        if values['max_price'] is not None:
            queryset = queryset.filter(price__lte=values['max_price'])
        order = {'price_asc': ('price', '-created_at', '-id'), 'price_desc': ('-price', '-created_at', '-id'), 'title': ('title', '-id')}.get(values['sort'], ('-created_at', '-id'))
        queryset = queryset.order_by(*order)
    else:
        queryset = queryset.none()
    page = Paginator(queryset, 6).get_page(params.get('page'))
    return form, page
