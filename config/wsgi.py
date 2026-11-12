"""WSGI config for the Resume & Job Matcher project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Data Manager: load and check every saved record once at startup
from matcher.managers.data_manager import JsonRepository  # noqa: E402

JsonRepository().check_on_startup()
