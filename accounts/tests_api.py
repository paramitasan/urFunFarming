from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Profile
from accounts.forms import ROLE_ERROR

PASSWORD = 'tomato-Balcony-42'
USER_FIELDS = {'username', 'display_name', 'is_grower', 'is_buyer', 'last_login'}


class ApiAuthTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('idris_k', password=PASSWORD, email='idris@example.com')
        self.profile = Profile.objects.create(user=self.user, display_name='Muhammad Idris', is_grower=True)

    def use_token(self, key):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {key}')


class RegisterApiTest(APITestCase):
    url = reverse('accounts_api:register')

    def data(self, **extra):
        return {
            'display_name': 'Muhammad Idris',
            'username': 'idris_k',
            'password1': PASSWORD,
            'password2': PASSWORD,
            'is_grower': True,
            **extra,
        }

    def test_register_creates_user_and_profile(self):
        response = self.client.post(self.url, self.data(is_buyer=True), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(set(response.data), USER_FIELDS)
        self.assertEqual(response.data['display_name'], 'Muhammad Idris')
        self.assertTrue(response.data['is_grower'])
        self.assertTrue(response.data['is_buyer'])
        self.assertIsNone(response.data['last_login'])
        user = User.objects.get(username='idris_k')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.profile.display_name, 'Muhammad Idris')

    def test_register_accepts_form_data(self):
        response = self.client.post(self.url, self.data(is_grower='on'))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_does_not_return_password_or_token(self):
        response = self.client.post(self.url, self.data(), format='json')
        self.assertNotIn('password', response.data)
        self.assertNotIn('token', response.data)
        self.assertNotIn(PASSWORD, response.content.decode())

    def test_register_without_role_gives_role_error(self):
        response = self.client.post(self.url, self.data(is_grower=False), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['errors']['__all__'], [ROLE_ERROR])
        self.assertFalse(User.objects.exists())

    def test_register_password_mismatch_gives_field_error(self):
        response = self.client.post(self.url, self.data(password2='something-Else-99'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password2', response.data['errors'])

    def test_register_duplicate_username_gives_field_error(self):
        User.objects.create_user('idris_k', password=PASSWORD)
        response = self.client.post(self.url, self.data(), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data['errors'])

    def test_register_missing_fields_gives_field_errors(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ('display_name', 'username', 'password1', 'password2'):
            self.assertIn(field, response.data['errors'])

    def test_register_json_that_is_not_an_object_gives_400(self):
        for body in ('[]', '"idris_k"', '42'):
            response = self.client.post(self.url, body, content_type='application/json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('__all__', response.data['errors'])

    def test_register_malformed_json_gives_400(self):
        response = self.client.post(self.url, '{bad', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_ignores_a_bad_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')
        response = self.client.post(self.url, self.data(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_rejects_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class LoginApiTest(ApiAuthTestCase):
    url = reverse('accounts_api:login')

    def login(self, password=PASSWORD):
        return self.client.post(self.url, {'username': 'idris_k', 'password': password}, format='json')

    def test_login_returns_token_and_user_fields(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), USER_FIELDS | {'token'})
        self.assertEqual(response.data['token'], Token.objects.get(user=self.user).key)
        self.assertEqual(response.data['username'], 'idris_k')
        self.assertEqual(response.data['display_name'], 'Muhammad Idris')
        self.assertTrue(response.data['is_grower'])
        self.assertFalse(response.data['is_buyer'])

    def test_login_sets_last_login_from_the_user(self):
        self.assertIsNone(self.user.last_login)
        response = self.login()
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertEqual(response.data['last_login'], self.user.last_login.astimezone().isoformat())
        self.assertNotIn('last_login', response.cookies)

    def test_login_does_not_start_a_session(self):
        self.login()
        self.assertNotIn('sessionid', self.client.cookies)

    def test_login_twice_returns_the_same_token(self):
        first = self.login().data['token']
        second = self.login().data['token']
        self.assertEqual(first, second)
        self.assertEqual(Token.objects.filter(user=self.user).count(), 1)

    def test_login_does_not_return_password_or_email(self):
        content = self.login().content.decode()
        self.assertNotIn(PASSWORD, content)
        self.assertNotIn('idris@example.com', content)

    def test_login_wrong_password_gives_400_without_token(self):
        response = self.login(password='wrong-Password-1')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("don't match", response.data['errors']['__all__'][0])
        self.assertNotIn('token', response.data)
        self.assertFalse(Token.objects.exists())

    def test_login_inactive_user_gives_400(self):
        self.user.is_active = False
        self.user.save()
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Token.objects.exists())

    def test_login_missing_fields_gives_field_errors(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data['errors'])
        self.assertIn('password', response.data['errors'])

    def test_login_json_that_is_not_an_object_gives_400(self):
        for body in ('[]', '"idris_k"', '42'):
            response = self.client.post(self.url, body, content_type='application/json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(Token.objects.exists())

    def test_login_ignores_a_bad_token(self):
        self.use_token('not-a-real-token')
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

    def test_login_user_without_profile_falls_back_to_username(self):
        self.profile.delete()
        response = self.login()
        self.assertEqual(response.data['display_name'], 'idris_k')
        self.assertFalse(response.data['is_grower'])
        self.assertFalse(response.data['is_buyer'])


class MeApiTest(ApiAuthTestCase):
    url = reverse('accounts_api:me')

    def test_me_with_token_returns_own_fields(self):
        self.use_token(Token.objects.create(user=self.user).key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), USER_FIELDS)
        self.assertEqual(response.data['username'], 'idris_k')
        self.assertNotIn('token', response.data)

    def test_me_returns_the_token_owner_only(self):
        other = User.objects.create_user('paramita', password=PASSWORD)
        Profile.objects.create(user=other, display_name='Paramita', is_buyer=True)
        Token.objects.create(user=self.user)
        self.use_token(Token.objects.create(user=other).key)
        response = self.client.get(self.url)
        self.assertEqual(response.data['username'], 'paramita')
        self.assertNotIn(Token.objects.get(user=self.user).key, response.content.decode())

    def test_me_without_token_gives_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response['WWW-Authenticate'], 'Token')

    def test_me_with_bad_token_gives_401(self):
        self.use_token('not-a-real-token')
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_with_wrong_scheme_gives_401(self):
        key = Token.objects.create(user=self.user).key
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {key}')
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_with_token_of_inactive_user_gives_401(self):
        self.use_token(Token.objects.create(user=self.user).key)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_ignores_a_website_session(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutApiTest(ApiAuthTestCase):
    url = reverse('accounts_api:logout')

    def test_logout_deletes_the_token(self):
        key = Token.objects.create(user=self.user).key
        self.use_token(key)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(key=key).exists())

    def test_token_stops_working_after_logout(self):
        self.use_token(Token.objects.create(user=self.user).key)
        self.client.post(self.url)
        response = self.client.get(reverse('accounts_api:me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_only_deletes_own_token(self):
        other = User.objects.create_user('paramita', password=PASSWORD)
        other_token = Token.objects.create(user=other)
        self.use_token(Token.objects.create(user=self.user).key)
        self.client.post(self.url)
        self.assertTrue(Token.objects.filter(pk=other_token.pk).exists())

    def test_logout_without_token_gives_401(self):
        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_bad_token_gives_401(self):
        self.use_token('not-a-real-token')
        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_get(self):
        self.use_token(Token.objects.create(user=self.user).key)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_new_login_after_logout_gets_a_new_token(self):
        old = Token.objects.create(user=self.user).key
        self.use_token(old)
        self.client.post(self.url)
        self.client.credentials()
        response = self.client.post(
            reverse('accounts_api:login'), {'username': 'idris_k', 'password': PASSWORD}, format='json',
        )
        self.assertNotEqual(response.data['token'], old)


class WebsiteLoginUnchangedTest(ApiAuthTestCase):
    def test_website_login_still_uses_session_and_cookie(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'idris_k', 'password': PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertIn('sessionid', self.client.cookies)
        self.assertIn('last_login', response.cookies)
        self.assertFalse(Token.objects.exists())
