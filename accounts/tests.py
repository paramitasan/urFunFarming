from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile


class AccountTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('idris_k', password='tomato-Balcony-42')
        self.profile = Profile.objects.create(user=self.user, display_name='Muhammad Idris', is_grower=True)

    def login(self, **extra):
        data = {'username': 'idris_k', 'password': 'tomato-Balcony-42', **extra}
        return self.client.post(reverse('accounts:login'), data)


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


class LoginLogoutTest(AccountTestCase):
    def test_login_success_sets_last_login_cookie(self):
        response = self.login(remember_me='on')
        self.assertRedirects(response, reverse('main:home'))
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

    def test_logout_rejects_get(self):
        self.login(remember_me='on')
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_logged_out_user_is_sent_to_login(self):
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))


class SignedInPagesTest(AccountTestCase):
    def test_navbar_shows_display_name(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('main:home'))
        self.assertContains(response, 'Muhammad Idris')
        self.assertContains(response, 'class="avatar">MI<')
        self.assertNotContains(response, 'class="nav-login"')

    def test_home_shows_last_login_after_logging_in(self):
        self.login()
        response = self.client.get(reverse('main:home'))
        self.assertContains(response, 'Last login ')
        self.assertContains(response, 'Add buying any time.')

    def test_landing_stays_public(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log in')
        self.assertNotContains(response, 'Last login:')


class SessionPersistenceTest(AccountTestCase):
    def assert_still_signed_in(self):
        response = self.client.get(reverse('main:home'))
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
        self.assertRedirects(self.client.get(reverse('accounts:login')), reverse('main:home'))
        self.assertRedirects(self.client.get(reverse('accounts:register')), reverse('main:home'))
        self.assert_still_signed_in()


class JsonEndpointTest(AccountTestCase):
    def test_me_json_logged_out(self):
        response = self.client.get(reverse('accounts:me_json'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'is_authenticated': False})

    def test_me_json_logged_in(self):
        self.login()
        data = self.client.get(reverse('accounts:me_json')).json()
        self.assertTrue(data['is_authenticated'])
        self.assertEqual(data['username'], 'idris_k')
        self.assertEqual(data['display_name'], 'Muhammad Idris')
        self.assertTrue(data['is_grower'])
        self.assertFalse(data['is_buyer'])
        self.assertNotEqual(data['last_login'], 'Never')

    def test_profile_json_hides_contact_from_visitors(self):
        Profile.objects.filter(user=self.user).update(
            bio='Balcony grower', area='Tebet', city='Jakarta', phone='+62 812 3456 7890', contact_email='idris@example.com',
        )
        response = self.client.get(reverse('accounts:profile_json', args=['idris_k']))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['display_name'], 'Muhammad Idris')
        self.assertEqual(data['city'], 'Jakarta')
        self.assertEqual(
            set(data), {'username', 'display_name', 'is_grower', 'is_buyer', 'bio', 'area', 'city', 'created_at'},
        )
        self.assertNotIn('+62 812', response.content.decode())
        self.assertNotIn('idris@example.com', response.content.decode())

    def test_profile_json_shows_contact_to_members(self):
        Profile.objects.filter(user=self.user).update(phone='+62 812 3456 7890', contact_email='idris@example.com')
        member = User.objects.create_user('sekar_a', password='tomato-Balcony-42')
        self.client.force_login(member)
        data = self.client.get(reverse('accounts:profile_json', args=['idris_k'])).json()
        self.assertEqual(data['phone'], '+62 812 3456 7890')
        self.assertEqual(data['contact_email'], 'idris@example.com')

    def test_profile_json_unknown_user_is_404(self):
        response = self.client.get(reverse('accounts:profile_json', args=['nobody']))
        self.assertEqual(response.status_code, 404)


class AjaxAuthTest(AccountTestCase):
    def test_login_ajax_success(self):
        response = self.client.post(reverse('accounts:login_ajax'), {
            'username': 'idris_k', 'password': 'tomato-Balcony-42', 'remember_me': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success', 'redirect': reverse('main:home')})
        self.assertIn('sessionid', response.cookies)
        self.assertTrue(response.cookies['last_login'].value)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_ajax_failure(self):
        response = self.client.post(reverse('accounts:login_ajax'), {'username': 'idris_k', 'password': 'wrong'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn("don't match", data['errors']['__all__'][0])
        self.assertNotIn('sessionid', response.cookies)

    def test_login_ajax_rejects_get(self):
        self.assertEqual(self.client.get(reverse('accounts:login_ajax')).status_code, 405)

    def test_login_ajax_with_csrf_header(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('accounts:login'))
        token = client.cookies['csrftoken'].value
        data = {'username': 'idris_k', 'password': 'tomato-Balcony-42'}

        self.assertEqual(client.post(reverse('accounts:login_ajax'), data).status_code, 403)
        response = client.post(reverse('accounts:login_ajax'), data, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertIn('sessionid', response.cookies)

    def test_ajax_views_send_signed_in_users_home(self):
        self.login(remember_me='on')
        for name in ('accounts:login_ajax', 'accounts:register_ajax'):
            response = self.client.post(reverse(name), {})
            self.assertEqual(response.json(), {'status': 'success', 'redirect': reverse('main:home')})
        self.assertEqual(User.objects.count(), 1)

    def test_register_ajax_validation_errors(self):
        response = self.client.post(reverse('accounts:register_ajax'), {
            'display_name': 'Sekar',
            'username': 'idris_k',
            'password1': 'tomato-Balcony-42',
            'password2': 'something-Else-99',
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('username', data['errors'])
        self.assertIn('password2', data['errors'])
        self.assertIn('Pick at least one role', data['errors']['__all__'][0])
        self.assertEqual(User.objects.count(), 1)

    def test_register_ajax_success(self):
        response = self.client.post(reverse('accounts:register_ajax'), {
            'display_name': 'Sekar',
            'username': 'sekar_a',
            'password1': 'tomato-Balcony-42',
            'password2': 'tomato-Balcony-42',
            'is_buyer': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success', 'redirect': reverse('accounts:login')})
        self.assertTrue(Profile.objects.get(user__username='sekar_a').is_buyer)


class ProfilePageTest(AccountTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.data = {
            'save_profile': '1',
            'display_name': 'Idris K',
            'bio': 'Balcony grower in Tebet.',
            'location': '31.74.01.1001',
            'phone': '+62 812 3456 7890',
            'contact_email': 'idris@example.com',
            'is_grower': 'on',
            'is_buyer': 'on',
        }

    def change_password(self, old, **extra):
        data = {
            'change_password': '1',
            'old_password': old,
            'new_password1': 'chili-Rooftop-77',
            'new_password2': 'chili-Rooftop-77',
        }
        return self.client.post(reverse('accounts:profile'), data, **extra)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))

    def test_page_renders_own_profile(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')
        self.assertContains(response, '@idris_k')
        self.assertContains(response, '+ Add buyer')

    def test_profile_update_success(self):
        response = self.client.post(reverse('accounts:profile'), self.data, follow=True)
        self.assertRedirects(response, reverse('accounts:profile'))
        self.assertContains(response, 'Profile saved.')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.display_name, 'Idris K')
        self.assertEqual((self.profile.area, self.profile.city), ('Tebet', 'Jakarta Selatan'))
        self.assertEqual(self.profile.adm4_code, '31.74.01.1001')
        self.assertTrue(self.profile.is_buyer)

    def test_profile_update_with_fetch(self):
        response = self.client.post(reverse('accounts:profile'), self.data, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['profile']['initials'], 'IK')

    def test_location_is_picked_from_the_list(self):
        response = self.client.get(reverse('accounts:profile'))
        # Grouped by "District, City" so it works without JavaScript too
        self.assertContains(response, '<optgroup label="Tebet, Jakarta Selatan">', html=False)
        self.assertContains(response, '<option value="31.74.01.1001">Tebet Timur</option>')

    def test_unknown_location_code_is_rejected(self):
        self.data['location'] = '99.99.99.9999'
        response = self.client.post(reverse('accounts:profile'), self.data, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 400)
        self.assertIn('location', response.json()['errors'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.adm4_code, '')

    def test_saved_location_is_preselected_and_can_be_cleared(self):
        self.client.post(reverse('accounts:profile'), self.data)
        response = self.client.get(reverse('accounts:profile'))
        self.assertContains(response, '<option value="31.74.01.1001" selected>Tebet Timur</option>')
        self.client.post(reverse('accounts:profile'), {**self.data, 'location': ''})
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.adm4_code, self.profile.area, self.profile.city), ('', '', ''))

    def test_bio_over_300_characters(self):
        self.data['bio'] = 'a' * 301
        response = self.client.post(reverse('accounts:profile'), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['profile_form'].has_error('bio'))

        response = self.client.post(reverse('accounts:profile'), self.data, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 400)
        self.assertIn('bio', response.json()['errors'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, '')

    def test_no_role_selected(self):
        del self.data['is_grower']
        del self.data['is_buyer']
        response = self.client.post(reverse('accounts:profile'), self.data, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('Pick at least one role', response.json()['errors']['__all__'][0])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_grower)

    def test_password_change_keeps_user_logged_in(self):
        response = self.change_password('tomato-Balcony-42', follow=True)
        self.assertContains(response, 'Password updated.')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('chili-Rooftop-77'))
        response = self.client.get(reverse('main:show_main'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_wrong_current_password(self):
        response = self.change_password('wrong', HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 400)
        self.assertIn('old_password', response.json()['errors'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('tomato-Balcony-42'))

    def test_cannot_change_another_users_profile(self):
        other = User.objects.create_user('sekar_a', password='tomato-Balcony-42')
        other_profile = Profile.objects.create(user=other, display_name='Sekar', is_buyer=True)
        self.data.update({'user': other.pk, 'username': 'sekar_a', 'id': other_profile.pk})
        self.client.post(reverse('accounts:profile'), self.data)
        other_profile.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(other_profile.display_name, 'Sekar')
        self.assertEqual(self.profile.display_name, 'Idris K')
