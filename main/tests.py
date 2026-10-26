import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile


class LandingPageTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_landing_page_url_exists(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_landing_page_uses_main_template(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertTemplateUsed(response, 'landing.html')

    def test_landing_sky_follows_jakarta_time(self):
        jakarta = ZoneInfo('Asia/Jakarta')
        for hour, period in [(8, 'morning'), (13, 'afternoon'), (17, 'evening'), (22, 'night')]:
            fake_now = datetime.datetime(2026, 10, 23, hour, 0, tzinfo=jakarta)
            with self.subTest(hour=hour), patch('main.views.timezone.localtime', return_value=fake_now):
                response = self.client.get(reverse('main:show_main'))
                self.assertContains(response, f'class="hero" data-period="{period}"')
                if period == 'night':
                    self.assertContains(response, 'class="moon"')
                else:
                    self.assertNotContains(response, 'class="moon"')

class HomePageTest(TestCase):
    def make_user(self, username, is_grower=False, is_buyer=False):
        user = User.objects.create_user(username, password='tomato-Balcony-42')
        Profile.objects.create(user=user, display_name='Idris', is_grower=is_grower, is_buyer=is_buyer, area='Tebet', city='Jakarta')
        return user

    def setUp(self):
        self.grower = self.make_user('grower', is_grower=True)
        self.buyer = self.make_user('buyer', is_buyer=True)
        self.both = self.make_user('both', is_grower=True, is_buyer=True)

    def home_as(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('main:home'))

    def test_home_requires_login(self):
        response = self.client.get(reverse('main:home'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))

    def test_landing_redirects_members_to_home(self):
        self.client.force_login(self.buyer)
        self.assertRedirects(self.client.get(reverse('main:show_main')), reverse('main:home'))

    def test_login_redirect_setting(self):
        self.assertEqual(settings.LOGIN_REDIRECT_URL, '/home/')

    def test_greeting_follows_jakarta_time(self):
        jakarta = ZoneInfo('Asia/Jakarta')
        cases = [(6, 'morning'), (10, 'morning'), (11, 'afternoon'), (14, 'afternoon'),
                 (15, 'evening'), (18, 'evening'), (19, 'night'), (23, 'night')]
        self.client.force_login(self.grower)
        for hour, greeting in cases:
            fake_now = datetime.datetime(2026, 10, 23, hour, 30, tzinfo=jakarta)
            with self.subTest(hour=hour), patch('main.views.timezone.localtime', return_value=fake_now):
                response = self.client.get(reverse('main:home'))
                self.assertContains(response, f'Good {greeting},')
                self.assertContains(response, 'Idris.')
                self.assertContains(response, 'Friday, 23 October')
                self.assertContains(response, f'data-period="{greeting}"')
                if greeting == 'night':
                    self.assertContains(response, 'class="moon"')
                else:
                    self.assertNotContains(response, 'class="moon"')

    def test_one_sun_picked_by_period(self):
        jakarta = ZoneInfo('Asia/Jakarta')
        self.client.force_login(self.grower)
        for hour, sun in [(8, 'img/sun.svg'), (13, 'img/sun.svg'), (17, 'img/sun-evening.svg')]:
            fake_now = datetime.datetime(2026, 10, 23, hour, 0, tzinfo=jakarta)
            with self.subTest(hour=hour), patch('main.views.timezone.localtime', return_value=fake_now):
                response = self.client.get(reverse('main:home'))
                self.assertContains(response, 'class="sun"', count=1)
                self.assertContains(response, sun)

        self.client.logout()
        midday = datetime.datetime(2026, 10, 23, 13, 0, tzinfo=jakarta)
        with patch('main.views.timezone.localtime', return_value=midday):
            landing = self.client.get(reverse('main:show_main'))
        self.assertContains(landing, 'class="sun"', count=1)
        self.assertNotContains(landing, 'sun-evening.svg')

    def test_hero_shows_last_login_roles_and_area(self):
        self.client.force_login(self.both)
        self.client.cookies['last_login'] = '2026-10-23 08:12:45.123456'
        response = self.client.get(reverse('main:home'))
        self.assertContains(response, 'Last login 23 Oct, 08:12')
        self.assertContains(response, 'Grower and buyer · Tebet, Jakarta')
        self.assertContains(response, reverse('accounts:profile'))

    def test_grower_tiles_only_for_growers(self):
        grower_page = self.home_as(self.grower)
        self.assertContains(grower_page, 'Your growing tools')
        self.assertContains(grower_page, 'Around the neighborhood')
        self.assertContains(grower_page, 'class="launch-tile"', count=6)
        self.assertNotContains(grower_page, 'MODULE')

        buyer_page = self.home_as(self.buyer)
        self.assertNotContains(buyer_page, 'Your growing tools')
        self.assertContains(buyer_page, 'Around the neighborhood')
        self.assertContains(buyer_page, 'class="launch-tile"', count=3)

        both_page = self.home_as(self.both)
        self.assertContains(both_page, 'Your growing tools')
        self.assertContains(both_page, 'Around the neighborhood')
        self.assertContains(both_page, 'class="launch-tile"', count=6)
        self.assertNotContains(both_page, 'Where to?')

    def test_subnav_only_for_growers_on_home(self):
        self.assertContains(self.home_as(self.grower), 'class="subnav"')
        self.assertContains(self.home_as(self.both), 'class="subnav"')
        self.assertNotContains(self.home_as(self.buyer), 'class="subnav"')

        self.client.force_login(self.grower)
        self.assertNotContains(self.client.get(reverse('accounts:profile')), 'class="subnav"')

    def test_home_link_only_when_logged_in(self):
        visitor_page = self.client.get(reverse('main:show_main'))
        self.assertNotContains(visitor_page, 'data-label="Home"')
        self.assertContains(visitor_page, 'class="logo" href="/"')

        member_page = self.home_as(self.buyer)
        self.assertContains(member_page, 'data-label="Home" aria-current="page"')
        self.assertContains(member_page, 'class="logo" href="/home/"')

    def test_explore_gardens_replaces_gardens(self):
        for response in (self.client.get(reverse('main:show_main')), self.home_as(self.grower)):
            self.assertContains(response, 'data-label="Explore gardens"')
            self.assertNotContains(response, 'data-label="Gardens"')

    def test_role_band_and_chips(self):
        grower_page = self.home_as(self.grower)
        self.assertContains(grower_page, 'Add buying any time.')
        self.assertContains(grower_page, '+ Add buyer')


        buyer_page = self.home_as(self.buyer)
        self.assertContains(buyer_page, 'Add growing any time.')
        self.assertContains(buyer_page, '+ Add grower')

        both_page = self.home_as(self.both)
        self.assertNotContains(both_page, 'class="role-band"')
        self.assertNotContains(both_page, '+ Add')

    def test_home_loads_the_shared_hero_animation(self):
        response = self.home_as(self.grower)
        self.assertContains(response, 'js/hero-motion.js')
        self.assertContains(response, 'js/home-motion.js')
        self.client.logout()
        self.assertContains(self.client.get(reverse('main:show_main')), 'js/hero-motion.js')

    def test_user_without_profile_gets_one(self):
        admin = User.objects.create_user('admin_k', password='tomato-Balcony-42')
        response = self.home_as(admin)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=admin).exists())
