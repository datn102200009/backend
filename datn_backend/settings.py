"""
Django settings module - Route to appropriate settings based on environment.

This wrapper imports settings from the appropriate module based on DJANGO_SETTINGS_MODULE
or falls back to development settings.

Usage:
    Development: python manage.py runserver  # Uses datn_backend.settings.dev
    Production: DJANGO_SETTINGS_MODULE=datn_backend.settings.production gunicorn ...
"""

# Import from development settings by default
# This file is kept for backward compatibility with Django's settings discovery
from .settings.dev import *  # noqa
