"""
WSGI config for uff project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import logging
import os
from pathlib import Path

import django
from django.conf import settings
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uff.settings')

logger = logging.getLogger(__name__)


def collect_static_files():
    """Copy static files into STATIC_ROOT before the app starts.

    PWS has no build step that runs collectstatic, and with DEBUG off the
    manifest storage needs the files it writes. Gunicorn starts several
    workers at once, so a file lock lets one worker copy the files while the
    others wait for it to finish.
    """
    import fcntl  # Unix only; production runs on Linux

    static_root = Path(settings.STATIC_ROOT)
    static_root.mkdir(parents=True, exist_ok=True)
    with open(static_root.parent / '.collectstatic.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            call_command('collectstatic', interactive=False, verbosity=0)
        except Exception:
            logger.exception('collectstatic failed, so static files may be missing')
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


django.setup()
if settings.PRODUCTION:
    collect_static_files()

# WhiteNoise indexes STATIC_ROOT when the middleware loads, so this comes last.
application = get_wsgi_application()
