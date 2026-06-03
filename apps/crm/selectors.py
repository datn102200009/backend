from django.db.models import QuerySet

from apps.common.xlib.exceptions import NotFoundException
from apps.crm.models import Customer


def customer_list() -> QuerySet:
    return Customer.objects.filter(is_active=True).order_by("-created_at", "id")


def customer_detail(*, customer_id: str) -> Customer:
    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        raise NotFoundException("Khách hàng không tồn tại.")
    return customer
