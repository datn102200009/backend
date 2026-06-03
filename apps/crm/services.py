from decimal import Decimal

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
    credit_limit: Decimal = Decimal("0.00"),
    payment_terms: str = "NET30",
    is_credit_locked: bool = False,
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
        credit_limit=credit_limit,
        payment_terms=payment_terms,
        is_credit_locked=is_credit_locked,
    )

    create_system_log(
        user=user,
        action="create",
        table_name="customer",
        record_id=str(customer.id),
        new_value={
            "name": name,
            "customer_name": customer_name,
            "credit_limit": str(credit_limit),
            "payment_terms": payment_terms,
            "is_credit_locked": is_credit_locked,
        },
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
    credit_limit: Decimal = None,
    payment_terms: str = None,
    is_credit_locked: bool = None,
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

    if credit_limit is not None:
        customer.credit_limit = credit_limit
    if payment_terms is not None:
        customer.payment_terms = payment_terms
    if is_credit_locked is not None:
        customer.is_credit_locked = is_credit_locked

    customer.save()

    create_system_log(
        user=user,
        action="update",
        table_name="customer",
        record_id=str(customer.id),
        new_value={
            "name": name,
            "customer_name": customer_name,
            "credit_limit": str(customer.credit_limit),
            "payment_terms": customer.payment_terms,
            "is_credit_locked": customer.is_credit_locked,
        },
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
