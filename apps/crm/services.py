from django.db import transaction

from apps.accounts.models import User
from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.crm.models import Customer


@transaction.atomic
def customer_create(
    *,
    user: User,
    name: str,
    customer_name: str,
    customer_group: str = None,
    contact_email: str = None,
    contact_phone: str = None,
    address: str = None,
) -> Customer:
    PermissionChecker.check_permission(user, "crm.customer_create")

    if Customer.objects.filter(name=name).exists():
        raise ValidationException("Mã khách hàng đã tồn tại.")

    customer = Customer.objects.create(
        name=name,
        customer_name=customer_name,
        customer_group=customer_group,
        contact_email=contact_email,
        contact_phone=contact_phone,
        address=address,
    )

    create_system_log(
        user=user,
        action="create",
        table_name="customer",
        record_id=str(customer.id),
        new_value={"name": name, "customer_name": customer_name},
    )
    return customer


@transaction.atomic
def customer_update(
    *,
    user: User,
    customer_id: str,
    name: str,
    customer_name: str,
    customer_group: str = None,
    contact_email: str = None,
    contact_phone: str = None,
    address: str = None,
) -> Customer:
    PermissionChecker.check_permission(user, "crm.customer_update")

    customer = Customer.objects.select_for_update().filter(id=customer_id).first()
    if not customer:
        raise NotFoundException("Khách hàng không tồn tại.")

    if Customer.objects.filter(name=name).exclude(id=customer_id).exists():
        raise ValidationException("Mã khách hàng đã tồn tại ở bản ghi khác.")

    customer.name = name
    customer.customer_name = customer_name
    customer.customer_group = customer_group
    customer.contact_email = contact_email
    customer.contact_phone = contact_phone
    customer.address = address
    customer.save()

    create_system_log(
        user=user,
        action="update",
        table_name="customer",
        record_id=str(customer.id),
        new_value={"name": name, "customer_name": customer_name},
    )
    return customer


@transaction.atomic
def customer_delete(*, user: User, customer_id: str) -> None:
    PermissionChecker.check_permission(user, "crm.customer_delete")

    customer = Customer.objects.select_for_update().filter(id=customer_id).first()
    if not customer:
        raise NotFoundException("Khách hàng không tồn tại.")

    # Ràng buộc: Kiểm tra xem đã có SalesOrder liên kết hay chưa
    from apps.sales.models import SalesOrder

    if SalesOrder.objects.filter(customer=customer).exists():
        raise ValidationException("Không thể xóa khách hàng đã có đơn bán hàng.")

    customer.delete()

    create_system_log(user=user, action="delete", table_name="customer", record_id=str(customer_id))
