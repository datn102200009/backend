"""
Test settings for pytest.
Uses in-memory SQLite database for fast tests.
"""

from datn_backend.settings.dev import *

# Use a consistent SECRET_KEY for testing
SECRET_KEY = "test-secret-key-for-testing-only"

# Override database to use SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable serialization warning
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# Speed up password hashing
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
