import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Base model with common fields for all models.
    Provides UUID as primary key, timestamps, and is_active flag.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
