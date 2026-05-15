"""
Manufacturing models.

Note: BOM, BOMItem, and WorkOrder are defined in master_data.models
to maintain a single source of truth for these entities.
"""

from django.db import models

from apps.common.models import BaseModel
from apps.master_data.models import Item

# Models are defined in master_data to avoid duplication
