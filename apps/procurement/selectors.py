from django.db.models import QuerySet

from apps.common.xlib.exceptions import NotFoundException
from apps.procurement.models import Supplier


def supplier_list() -> QuerySet:
    return Supplier.objects.filter(is_active=True).order_by("-created_at")


def supplier_detail(*, supplier_id: str) -> Supplier:
    supplier = Supplier.objects.filter(id=supplier_id).first()
    if not supplier:
        raise NotFoundException("Nhà cung cấp không tồn tại.")
    return supplier
