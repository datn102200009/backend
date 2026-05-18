"""
Global pytest configuration for all tests.
Override database settings to use SQLite for testing.
"""

import os

import django
from django.conf import settings

# Override database to use SQLite for tests
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datn_backend.settings.dev")

    # Configure test database
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

    django.setup()
