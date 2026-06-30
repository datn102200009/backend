from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.procurement.models import Supplier


@transaction.atomic
def supplier_create(
    *,
    user: User,
    name: str,
    supplier_name: str,
    supplier_group: str = None,
    contact_email: str = None,
    contact_phone: str = None,
    address: str = None,
) -> Supplier:
    PermissionChecker.check_permission(user, "procurement.supplier_create")

    if Supplier.objects.filter(name=name).exists():
        raise ValidationException("Mã nhà cung cấp đã tồn tại.")

    supplier = Supplier.objects.create(
        name=name,
        supplier_name=supplier_name,
        supplier_group=supplier_group,
        contact_email=contact_email,
        contact_phone=contact_phone,
        address=address,
    )

    create_system_log(
        user=user,
        action="create",
        table_name="supplier",
        record_id=str(supplier.id),
        new_value={"name": name, "supplier_name": supplier_name},
        allowed_permissions=["procurement.supplier_view"],
    )
    return supplier


@transaction.atomic
def supplier_update(
    *,
    user: User,
    supplier_id: str,
    name: str,
    supplier_name: str,
    supplier_group: str = None,
    contact_email: str = None,
    contact_phone: str = None,
    address: str = None,
) -> Supplier:
    PermissionChecker.check_permission(user, "procurement.supplier_update")

    supplier = Supplier.objects.select_for_update().filter(id=supplier_id).first()
    if not supplier:
        raise NotFoundException("Nhà cung cấp không tồn tại.")

    if Supplier.objects.filter(name=name).exclude(id=supplier_id).exists():
        raise ValidationException("Mã nhà cung cấp đã tồn tại ở bản ghi khác.")

    supplier.name = name
    supplier.supplier_name = supplier_name
    supplier.supplier_group = supplier_group
    supplier.contact_email = contact_email
    supplier.contact_phone = contact_phone
    supplier.address = address
    supplier.save()

    create_system_log(
        user=user,
        action="update",
        table_name="supplier",
        record_id=str(supplier.id),
        new_value={"name": name, "supplier_name": supplier_name},
        allowed_permissions=["procurement.supplier_view"],
    )
    return supplier


@transaction.atomic
def supplier_delete(*, user: User, supplier_id: str) -> None:
    PermissionChecker.check_permission(user, "procurement.supplier_delete")

    supplier = Supplier.objects.select_for_update().filter(id=supplier_id).first()
    if not supplier:
        raise NotFoundException("Nhà cung cấp không tồn tại.")

    # Ràng buộc: Kiểm tra xem đã có PurchaseOrder liên kết hay chưa
    from apps.purchasing.models import PurchaseOrder

    if PurchaseOrder.objects.filter(vendor=supplier).exists():
        raise ValidationException("Không thể xóa nhà cung cấp đã có đơn mua hàng.")

    supplier.delete()

    create_system_log(
        user=user,
        action="delete",
        table_name="supplier",
        record_id=str(supplier_id),
        allowed_permissions=["procurement.supplier_view"],
    )
