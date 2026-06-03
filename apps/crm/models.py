from django.db import models

from apps.common.models import BaseModel


class Customer(BaseModel):
    """
    Customer information.
    """

    name = models.CharField(max_length=255, unique=True)
    customer_name = models.CharField(max_length=255)
    customer_group = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Hạn mức nợ")
    payment_terms = models.CharField(max_length=50, default="NET30", verbose_name="Điều khoản thanh toán")
    is_credit_locked = models.BooleanField(default=False, verbose_name="Khóa tín dụng chủ động")

    class Meta:
        db_table = "customer"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return self.name
