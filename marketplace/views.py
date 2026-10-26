import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import BadRequest
from django.core.paginator import Paginator
from django.db.models import Q
from django.forms.models import model_to_dict
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.views import form_errors
from marketplace.dates import jakarta_today
from marketplace.forms import ListingFilterForm, ListingForm, PickupWeatherForm
from marketplace.models import HarvestListing
from marketplace.weather import WeatherUnavailable, filter_pickup_times, forecast


def _ajax(request):
    return request.headers.get('X-Requested-With') == 'fetch' or request.headers.get('HX-Request') == 'true'


def _json_error(message, status, **extra):
    return JsonResponse({'status': 'error', 'message': message, **extra}, status=status)


def _member(request, api=False, grower=False):
    if not request.user.is_authenticated:
        response = redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if api or _ajax(request):
            return _json_error('Log in to continue.', 401, redirect=response.url)
        return response
    if grower and not getattr(getattr(request.user, 'profile', None), 'is_grower', False):
        if api or _ajax(request):
            return _json_error('Add the grower role to your profile before listing a harvest.', 403)
        return render(request, 'marketplace/grower_required.html', status=403)
    return None


def _listings():
    return HarvestListing.objects.select_related('owner', 'owner__profile')


def _visible(request, pk):
    return get_object_or_404(_listings().visible_to(request.user), pk=pk)


def _catalog(request, mine=False):
    params = request.GET.copy()
    params.setdefault('availability', 'any' if mine else 'now')
    params.setdefault('sort', 'newest')
    form = ListingFilterForm(params)
    queryset = _listings().filter(owner=request.user) if mine else _listings().public()
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
    page = Paginator(queryset, 6).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    return {
        'filter_form': form, 'page_obj': page, 'listing_count': page.paginator.count,
        'page_numbers': list(page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)),
        'filter_query': query.urlencode(), 'mine': mine,
        'areas': HarvestListing.objects.public().order_by('area').values_list('area', flat=True).distinct(),
        'is_grower': bool(getattr(getattr(request.user, 'profile', None), 'is_grower', False)),
    }


@require_GET
def index(request):
    context = _catalog(request)
    return render(request, 'marketplace/_results.html' if _ajax(request) else 'marketplace/index.html', context)


@never_cache
@require_GET
def my_listings(request):
    denied = _member(request)
    if denied is not None:
        return denied
    return render(request, 'marketplace/_results.html' if _ajax(request) else 'marketplace/index.html', _catalog(request, mine=True))


@never_cache
@require_GET
def detail(request, pk):
    return render(request, 'marketplace/detail.html', {'listing': _visible(request, pk), 'weather_form': PickupWeatherForm()})


def _payload(request):
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            raise BadRequest('Send a valid JSON object.')
        if not isinstance(data, dict):
            raise BadRequest('Send a JSON object, rather than a list or scalar.')
        return data
    return request.POST.copy()


def _save(request, instance=None, api=False, partial=False):
    try:
        data = _payload(request)
    except BadRequest as error:
        return _json_error(str(error), 400)
    if partial:
        existing = model_to_dict(instance, fields=ListingForm.Meta.fields)
        existing.update(data)
        data = existing
    if api and instance is None:
        data.setdefault('available_from', jakarta_today())
        data.setdefault('is_available', True)
        data.setdefault('price_quantity', '1')
        data.setdefault('city', HarvestListing.City.DEPOK)
    form = ListingForm(data, instance=instance)
    if form.is_valid():
        listing = form.save(commit=False)
        if instance is None:
            listing.owner = request.user
        listing.save()
        messages.success(request, 'Harvest updated.' if instance else 'Your harvest is now listed.')
        if api or _ajax(request):
            return JsonResponse({'status': 'success', 'listing': _serialize(listing, request), 'redirect': listing.get_absolute_url()}, status=201 if instance is None else 200)
        return redirect(listing)
    if api or _ajax(request):
        return _json_error('Please check the highlighted fields.', 400, errors=form_errors(form))
    return render(request, 'marketplace/form.html', {'form': form, 'listing': instance}, status=400)


@never_cache
@require_http_methods(['GET', 'POST'])
def create(request):
    denied = _member(request, grower=True)
    if denied is not None:
        return denied
    if request.method == 'POST':
        return _save(request)
    profile = request.user.profile
    initial = {'area': profile.area}
    if profile.city in HarvestListing.City.values:
        initial['city'] = profile.city
    return render(request, 'marketplace/form.html', {'form': ListingForm(initial=initial)})


@never_cache
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    denied = _member(request)
    if denied is not None:
        return denied
    listing = get_object_or_404(_listings(), pk=pk, owner=request.user)
    if request.method == 'POST':
        return _save(request, listing)
    return render(request, 'marketplace/form.html', {'form': ListingForm(instance=listing), 'listing': listing})


def _delete(request, listing, api=False):
    listing.delete()
    messages.success(request, 'Harvest listing deleted.')
    target = reverse('marketplace:mine')
    if api or _ajax(request):
        return JsonResponse({'status': 'success', 'redirect': target})
    return redirect(target)


@never_cache
@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    denied = _member(request)
    if denied is not None:
        return denied
    listing = get_object_or_404(_listings(), pk=pk, owner=request.user)
    if request.method == 'POST':
        return _delete(request, listing)
    return render(request, 'marketplace/delete.html', {'listing': listing})


def _serialize(listing, request, include_contact=False):
    data = {
        'id': str(listing.pk), 'title': listing.title, 'description': listing.description,
        'category': listing.category, 'quantity': str(listing.quantity), 'unit': listing.unit,
        'price': str(listing.price), 'price_quantity': str(listing.price_quantity),
        'price_label': listing.price_label, 'quantity_label': listing.quantity_label,
        'area': listing.area, 'city': listing.city, 'image_url': listing.image_url,
        'available_from': listing.available_from.isoformat(),
        'available_until': listing.available_until.isoformat() if listing.available_until else None,
        'is_available': listing.is_available, 'is_demo': listing.is_demo,
        'owner': {'username': listing.owner.username, 'display_name': listing.grower_name},
        'can_manage': request.user.is_authenticated and request.user.pk == listing.owner_id,
        'url': listing.get_absolute_url(), 'created_at': listing.created_at.isoformat(),
        'updated_at': listing.updated_at.isoformat(),
    }
    if include_contact and request.user.is_authenticated:
        profile = getattr(listing.owner, 'profile', None)
        data['contact'] = {'phone': profile.phone if profile else '', 'email': profile.contact_email if profile else ''}
    return data


@never_cache
@require_http_methods(['GET', 'POST'])
def listings_json(request):
    if request.method == 'POST':
        denied = _member(request, api=True, grower=True)
        return denied if denied is not None else _save(request, api=True)
    context = _catalog(request)
    if not context['filter_form'].is_valid():
        return _json_error('Invalid filters.', 400, errors=form_errors(context['filter_form']))
    page = context['page_obj']
    return JsonResponse({'count': page.paginator.count, 'page': page.number, 'pages': page.paginator.num_pages, 'results': [_serialize(item, request) for item in page]})


@never_cache
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def listing_json(request, pk):
    if request.method == 'GET':
        try:
            listing = _visible(request, pk)
        except Http404:
            return _json_error('Harvest listing not found.', 404)
        return JsonResponse(_serialize(listing, request, include_contact=True))
    denied = _member(request, api=True)
    if denied is not None:
        return denied
    listing = _listings().filter(pk=pk, owner=request.user).first()
    if listing is None:
        return _json_error('Harvest listing not found.', 404)
    if request.method == 'DELETE':
        return _delete(request, listing, api=True)
    return _save(request, listing, api=True, partial=request.method == 'PATCH')


@never_cache
@require_GET
def pickup_weather(request, pk):
    listing = _visible(request, pk)
    form = PickupWeatherForm(request.GET)
    context = {'listing': listing, 'weather_form': form, 'weather_checked': True}
    status = 200
    if form.is_valid():
        try:
            data = forecast(listing.city)
            context.update(weather_slots=filter_pickup_times(data, form.cleaned_data, listing), weather_fetched_at=data['fetched_at'])
        except WeatherUnavailable as error:
            context['weather_error'] = str(error)
            status = 503
    else:
        status = 400
    if request.headers.get('Accept') == 'application/json':
        if not form.is_valid():
            return _json_error('Invalid pickup filters.', 400, errors=form_errors(form))
        if context.get('weather_error'):
            return _json_error(context['weather_error'], 503)
        return JsonResponse({'source': 'Open-Meteo', 'city': listing.city, 'timezone': 'Asia/Jakarta', 'fetched_at': context['weather_fetched_at'], 'results': [{**s, 'time': s['time'].isoformat()} for s in context['weather_slots']]})
    return render(request, 'marketplace/_weather.html' if _ajax(request) else 'marketplace/detail.html', context, status=status)
