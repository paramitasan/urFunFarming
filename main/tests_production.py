import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings

SETTING_VARS = ('PRODUCTION', 'DEBUG', 'SECRET_KEY', 'SECURE_COOKIES')

# Imports the settings module in a fresh Python, the way PWS starts the app
PRINT_SETTINGS = (
    'import json, uff.settings as s; '
    'print(json.dumps({"DEBUG": s.DEBUG, "SECRET_KEY": s.SECRET_KEY, '
    '"SESSION_COOKIE_SECURE": s.SESSION_COOKIE_SECURE, "CSRF_COOKIE_SECURE": s.CSRF_COOKIE_SECURE}))'
)


def load_settings(**env):
    clean = {k: v for k, v in os.environ.items() if k not in SETTING_VARS}
    result = subprocess.run(
        [sys.executable, '-c', PRINT_SETTINGS],
        cwd=settings.BASE_DIR, env={**clean, **env}, capture_output=True, text=True,
    )
    return result


class SettingsFromEnvironmentTest(SimpleTestCase):
    def settings_for(self, **env):
        result = load_settings(**env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_local_defaults(self):
        s = self.settings_for()
        self.assertTrue(s['DEBUG'])
        self.assertIn('local-only', s['SECRET_KEY'])
        self.assertFalse(s['SESSION_COOKIE_SECURE'])
        self.assertFalse(s['CSRF_COOKIE_SECURE'])

    def test_production_turns_debug_off_and_cookies_secure(self):
        s = self.settings_for(PRODUCTION='true', SECRET_KEY='pws-secret')
        self.assertFalse(s['DEBUG'])
        self.assertEqual(s['SECRET_KEY'], 'pws-secret')
        self.assertTrue(s['SESSION_COOKIE_SECURE'])
        self.assertTrue(s['CSRF_COOKIE_SECURE'])

    def test_production_refuses_to_start_without_secret_key(self):
        result = load_settings(PRODUCTION='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set the SECRET_KEY environment variable', result.stderr)

    def test_debug_variable_overrides_the_default(self):
        self.assertFalse(self.settings_for(DEBUG='False')['DEBUG'])
        prod = self.settings_for(PRODUCTION='true', SECRET_KEY='k', DEBUG='true')
        self.assertTrue(prod['DEBUG'])
        self.assertFalse(prod['SESSION_COOKIE_SECURE'])   # never secure cookies while DEBUG is on

    def test_secure_cookies_can_be_turned_off_in_production(self):
        s = self.settings_for(PRODUCTION='true', SECRET_KEY='k', SECURE_COOKIES='false')
        self.assertFalse(s['SESSION_COOKIE_SECURE'])

    def test_committed_key_is_gone(self):
        source = (Path(settings.BASE_DIR) / 'uff' / 'settings.py').read_text()
        self.assertNotIn('vk0lknzp1', source)


class MediaWithoutDebugTest(SimpleTestCase):
    # The test runner already runs with DEBUG off, like PWS

    def setUp(self):
        self.media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.addCleanup(override.disable)
        os.makedirs(os.path.join(self.media, 'forum'))
        with open(os.path.join(self.media, 'forum', 'photo.png'), 'wb') as f:
            f.write(b'fake png bytes')

    def test_debug_is_off_here(self):
        self.assertFalse(settings.DEBUG)

    def test_uploaded_file_is_served(self):
        response = self.client.get('/media/forum/photo.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'fake png bytes')
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_missing_file_gives_404(self):
        self.assertEqual(self.client.get('/media/forum/nope.png').status_code, 404)

    def test_paths_outside_media_are_refused(self):
        # Django answers 400 (suspicious path) or 404, never the file
        for path in ('/media/../manage.py', '/media/%2e%2e/manage.py', '/media//etc/passwd'):
            response = self.client.get(path)
            self.assertIn(response.status_code, (400, 404), path)
            self.assertNotIn(b'DJANGO_SETTINGS_MODULE', response.content, path)

    def test_folder_listing_is_off(self):
        self.assertEqual(self.client.get('/media/forum/').status_code, 404)

    def test_only_reading_is_allowed(self):
        self.assertEqual(self.client.post('/media/forum/photo.png').status_code, 405)
