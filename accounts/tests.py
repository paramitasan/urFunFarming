from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile


class RegisterTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.data = {
            'display_name': 'Muhammad Idris',
            'username': 'idris_k',
            'password1': 'tomato-Balcony-42',
            'password2': 'tomato-Balcony-42',
            'is_grower': 'on',
        }

    def test_register_success_creates_user_and_profile(self):
        response = self.client.post(reverse('accounts:register'), self.data, follow=True)
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertContains(response, 'Your account has been created')

        profile = Profile.objects.get(user__username='idris_k')
        self.assertEqual(profile.display_name, 'Muhammad Idris')
        self.assertTrue(profile.is_grower)
        self.assertFalse(profile.is_buyer)
        self.assertEqual(profile.initials, 'MI')

    def test_register_password_mismatch(self):
        self.data['password2'] = 'something-Else-99'
        response = self.client.post(reverse('accounts:register'), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].has_error('password2'))
        self.assertFalse(User.objects.filter(username='idris_k').exists())

    def test_register_needs_a_role(self):
        del self.data['is_grower']
        response = self.client.post(reverse('accounts:register'), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pick at least one role')
        self.assertFalse(User.objects.filter(username='idris_k').exists())


class LoginLogoutTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('idris_k', password='tomato-Balcony-42')
        Profile.objects.create(user=self.user, display_name='Muhammad Idris', is_grower=True)

    def login(self, **extra):
        data = {'username': 'idris_k', 'password': 'tomato-Balcony-42', **extra}
        return self.client.post(reverse('accounts:login'), data)

    def test_login_success_sets_last_login_cookie(self):
        response = self.login(remember_me='on')
        self.assertRedirects(response, reverse('main:show_main'))
        self.assertIn('_auth_user_id', self.client.session)
        self.assertTrue(response.cookies['last_login'].value)

    def test_login_failure_shows_error(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'idris_k', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That username and password don&#x27;t match')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn('last_login', response.cookies)

    def test_remember_me_unchecked_ends_session_on_browser_close(self):
        self.login()
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_remember_me_checked_keeps_session(self):
        self.login(remember_me='on')
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_logout_deletes_last_login_cookie(self):
        self.login(remember_me='on')
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertEqual(response.cookies['last_login'].value, '')
        self.assertEqual(response.cookies['last_login']['max-age'], 0)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logged_out_user_is_sent_to_login(self):
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))


class SignedInLandingTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('idris_k', password='tomato-Balcony-42')
        Profile.objects.create(user=self.user, display_name='Muhammad Idris', is_grower=True)

    def test_navbar_shows_display_name(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('main:show_main'))
        self.assertContains(response, 'Muhammad Idris')
        self.assertContains(response, 'class="avatar">MI<')
        self.assertNotContains(response, 'class="nav-login"')

    def test_landing_shows_last_login_and_grower_copy(self):
        self.client.post(reverse('accounts:login'), {'username': 'idris_k', 'password': 'tomato-Balcony-42'})
        response = self.client.get(reverse('main:show_main'))
        self.assertContains(response, 'Last login: ')
        self.assertContains(response, 'Add buying any time.')
        self.assertContains(response, 'Your role')

    def test_landing_stays_public(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log in')
        self.assertNotContains(response, 'Last login:')


class SessionPersistenceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('idris_k', password='tomato-Balcony-42')
        Profile.objects.create(user=self.user, display_name='Muhammad Idris', is_grower=True)

    def login(self, **extra):
        data = {'username': 'idris_k', 'password': 'tomato-Balcony-42', **extra}
        return self.client.post(reverse('accounts:login'), data)

    def assert_still_signed_in(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user, self.user)
        self.assertContains(response, 'class="profile-button"')

    def test_session_survives_next_page(self):
        response = self.login(remember_me='on')
        self.assertIn('sessionid', response.cookies)
        self.assert_still_signed_in()
        self.assert_still_signed_in()

    def test_session_survives_next_page_without_remember_me(self):
        self.login()
        self.assert_still_signed_in()

    def test_signed_in_user_skips_login_and_register(self):
        self.login(remember_me='on')
        self.assertRedirects(self.client.get(reverse('accounts:login')), reverse('main:show_main'))
        self.assertRedirects(self.client.get(reverse('accounts:register')), reverse('main:show_main'))
        self.assert_still_signed_in()
