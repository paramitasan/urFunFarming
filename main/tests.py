from django.test import Client, TestCase
from django.urls import reverse


class LandingPageTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_landing_page_url_exists(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_landing_page_uses_main_template(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertTemplateUsed(response, 'landing.html')