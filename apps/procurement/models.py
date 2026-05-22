from django.db import models

from apps.common.models import BaseModel


class Supplier(BaseModel):
    """
    Supplier information.
    """

    name = models.CharField(max_length=255, unique=True)
    supplier_name = models.CharField(max_length=255)
    supplier_group = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "supplier"
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def __str__(self):
        return self.name
