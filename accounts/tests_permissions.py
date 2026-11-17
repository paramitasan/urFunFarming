from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from accounts.models import Profile
from accounts.permissions import IsGrower, IsOwnerOrReadOnly, check_object_permissions

# Stand-ins for any model a teammate protects: gardens use owner, forum uses author
OBJECTS = {}


@api_view(['GET'])
@permission_classes([IsGrower])
def grower_view(request):
    return Response({'ok': True})


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsOwnerOrReadOnly])
def owned_view(request, key):
    obj = OBJECTS[key]
    check_object_permissions(request, obj)
    return Response({'ok': True})


class PermissionTestCase(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.grower = User.objects.create_user('grower', password='x')
        Profile.objects.create(user=self.grower, display_name='Grower', is_grower=True)
        self.buyer = User.objects.create_user('buyer', password='x')
        Profile.objects.create(user=self.buyer, display_name='Buyer', is_buyer=True)
        OBJECTS.clear()
        OBJECTS['garden'] = SimpleNamespace(owner_id=self.grower.pk)
        OBJECTS['post'] = SimpleNamespace(author_id=self.grower.pk)
        OBJECTS['profile'] = SimpleNamespace(user_id=self.grower.pk)


class IsGrowerTest(PermissionTestCase):
    def call(self, user=None, token=None):
        headers = {'HTTP_AUTHORIZATION': f'Token {token}'} if token else {}
        request = self.factory.get('/', **headers)
        if user:
            force_authenticate(request, user=user)
        return grower_view(request)

    def test_grower_is_allowed(self):
        self.assertEqual(self.call(self.grower).status_code, status.HTTP_200_OK)

    def test_grower_with_real_token_is_allowed(self):
        key = Token.objects.create(user=self.grower).key
        self.assertEqual(self.call(token=key).status_code, status.HTTP_200_OK)

    def test_buyer_gets_403_with_message(self):
        response = self.call(self.buyer)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], IsGrower.message)

    def test_user_without_profile_gets_403(self):
        user = User.objects.create_user('noprofile', password='x')
        self.assertEqual(self.call(user).status_code, status.HTTP_403_FORBIDDEN)

    def test_no_login_gets_401(self):
        self.assertEqual(self.call().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bad_token_gets_401(self):
        self.assertEqual(self.call(token='not-a-real-token').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_user_is_refused(self):
        request = SimpleNamespace(user=AnonymousUser())
        self.assertFalse(IsGrower().has_permission(request, None))


class IsOwnerOrReadOnlyTest(PermissionTestCase):
    def call(self, method, key, user=None):
        request = getattr(self.factory, method)('/')
        if user:
            force_authenticate(request, user=user)
        return owned_view(request, key=key)

    def test_anyone_can_read(self):
        for user in (None, self.grower, self.buyer):
            self.assertEqual(self.call('get', 'garden', user).status_code, status.HTTP_200_OK)

    def test_owner_can_change_through_each_owner_field(self):
        for key in ('garden', 'post', 'profile'):
            for method in ('put', 'delete'):
                response = self.call(method, key, self.grower)
                self.assertEqual(response.status_code, status.HTTP_200_OK, (key, method))

    def test_other_user_gets_403_with_message(self):
        for key in ('garden', 'post', 'profile'):
            response = self.call('put', key, self.buyer)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, key)
            self.assertEqual(response.data['detail'], IsOwnerOrReadOnly.message)

    def test_no_login_cannot_change(self):
        self.assertEqual(self.call('delete', 'garden').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_object_without_owner_field_says_how_to_fix(self):
        with self.assertRaisesMessage(AttributeError, 'override get_owner_id'):
            IsOwnerOrReadOnly().get_owner_id(SimpleNamespace(garden_id=1))

    def test_subclass_can_point_at_another_owner(self):
        class IsGardenOwnerOrReadOnly(IsOwnerOrReadOnly):
            def get_owner_id(self, obj):
                return obj.garden.owner_id

        entry = SimpleNamespace(garden=SimpleNamespace(owner_id=self.grower.pk))
        request = SimpleNamespace(method='PUT', user=self.grower)
        self.assertTrue(IsGardenOwnerOrReadOnly().has_object_permission(request, None, entry))
        request.user = self.buyer
        self.assertFalse(IsGardenOwnerOrReadOnly().has_object_permission(request, None, entry))
