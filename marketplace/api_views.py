"""Flutter endpoints. Reuse the website's model, visibility and pickup rules."""
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsGrower, IsOwnerOrReadOnly
from marketplace.catalog import catalog_page, listings
from marketplace.forms import PickupWeatherForm
from marketplace.serializers import HarvestSerializer, HarvestWriteSerializer, MemberHarvestSerializer
from marketplace.weather import WeatherUnavailable, filter_pickup_times, forecast


@method_decorator(never_cache, name='dispatch')
class HarvestEndpoint(APIView):
    # The mobile session is separate even if a browser also has a website cookie.
    authentication_classes = [TokenAuthentication]

    def listing(self, request, pk):
        return get_object_or_404(listings().visible_to(request.user), pk=pk)

    def detail_data(self, request, listing):
        serializer = MemberHarvestSerializer if request.user.is_authenticated else HarvestSerializer
        return serializer(listing, context={'request': request}).data


class HarvestList(HarvestEndpoint):
    mine = False

    def get_permissions(self):
        if self.mine:
            return [IsAuthenticated()]
        return [IsGrower()] if self.request.method == 'POST' else [AllowAny()]

    def get(self, request):
        form, page = catalog_page(request.query_params, request.user, mine=self.mine)
        if not form.is_valid():
            return Response({'errors': dict(form.errors)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'count': page.paginator.count, 'page': page.number, 'pages': page.paginator.num_pages,
            'results': HarvestSerializer(page.object_list, many=True, context={'request': request}).data,
        })

    def post(self, request):
        form = HarvestWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        listing = form.save(owner=request.user)
        return Response(self.detail_data(request, listing), status=status.HTTP_201_CREATED)


class MyHarvests(HarvestList):
    mine = True
    http_method_names = ['get', 'head', 'options']


class HarvestDetail(HarvestEndpoint):
    def get_permissions(self):
        return ([AllowAny()] if self.request.method in ('GET', 'HEAD', 'OPTIONS')
                else [IsAuthenticated(), IsOwnerOrReadOnly()])

    def get(self, request, pk):
        return Response(self.detail_data(request, self.listing(request, pk)))

    def write(self, request, pk, *, partial):
        listing = self.listing(request, pk)
        self.check_object_permissions(request, listing)
        form = HarvestWriteSerializer(listing, data=request.data, partial=partial)
        form.is_valid(raise_exception=True)
        return Response(self.detail_data(request, form.save()))

    def put(self, request, pk):
        return self.write(request, pk, partial=False)

    def patch(self, request, pk):
        return self.write(request, pk, partial=True)

    def delete(self, request, pk):
        listing = self.listing(request, pk)
        self.check_object_permissions(request, listing)
        listing.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PickupTimes(HarvestEndpoint):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        listing = self.listing(request, pk)
        form = PickupWeatherForm(request.query_params)
        if not form.is_valid():
            return Response({'errors': dict(form.errors)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            data = forecast(listing.city)
        except WeatherUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        slots = filter_pickup_times(data, form.cleaned_data, listing)
        return Response({
            'source': 'BMKG', 'city': listing.city, 'timezone': 'Asia/Jakarta',
            'fetched_at': data['fetched_at'].isoformat(),
            'results': [{'time': s['time'].isoformat(), 'temp': s['temp'],
                         'rain_mm': s['rain_mm'], 'description': s['description']} for s in slots],
        })
