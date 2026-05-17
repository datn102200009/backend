"""
Django settings module router.
This is a wrapper that imports from the appropriate settings module.
"""

import os

# Get the environment (default to development)
ENVIRONMENT = os.environ.get("DJANGO_ENVIRONMENT", "development")

# Import from the appropriate settings module based on environment
if ENVIRONMENT == "production":
    from .settings.production import *  # noqa
else:
    from .settings.dev import *  # noqa
