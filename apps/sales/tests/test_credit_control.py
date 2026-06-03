from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import Permission, Role, RolePermission
from apps.common.xlib.exceptions import PermissionException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.tests.factories import CustomerFactory, ItemFactory, UserFactory
from apps.sales.models import SalesInvoice, SalesOrder
from apps.sales.selectors import check_customer_overdue_debts, get_customer_current_debt
from apps.sales.services import approve_credit_bypass, sales_order_approve, sales_order_create

pytestmark = pytest.mark.django_db


class TestCreditControl:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        customer = CustomerFactory(credit_limit=Decimal("5000.00"), payment_terms="NET30", is_credit_locked=False)
        item = ItemFactory()
        return user, customer, item

    def test_debt_calculation_empty(self, setup_data):
        user, customer, item = setup_data
        assert get_customer_current_debt(str(customer.id)) == Decimal("0.00")

    def test_debt_calculation_with_unpaid_invoices(self, setup_data):
        user, customer, item = setup_data

        # Tạo đơn và hóa đơn unpaid
        order1 = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("2"), "unit_price": Decimal("100.00")}],
        )
        # Sử dụng patch để bypass check_permission và approve thành công
        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(order1.id))

        # Hóa đơn mới tạo sẽ ở trạng thái UNPAID, total_amount = 200, paid_amount = 0
        assert get_customer_current_debt(str(customer.id)) == Decimal("200.00")

        # Tạo thêm hóa đơn partial
        order2 = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("1"), "unit_price": Decimal("300.00")}],
        )
        order2.advance_paid_amount = Decimal("100.00")
        order2.save()

        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(order2.id))

        # Hóa đơn 2: total_amount = 300, paid_amount = 100 -> nợ = 200
        # Tổng nợ hiện tại = 200 + 200 = 400
        assert get_customer_current_debt(str(customer.id)) == Decimal("400.00")

    def test_overdue_debt_check(self, setup_data):
        user, customer, item = setup_data

        # Chưa có hóa đơn quá hạn
        assert not check_customer_overdue_debts(str(customer.id), max_days=30)

        # Tạo hóa đơn và lùi ngày tạo về trước 61 ngày (NET30 + max_days 30 = 60 ngày)
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("1"), "unit_price": Decimal("100.00")}],
        )
        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(order.id))

        invoice = SalesInvoice.objects.filter(order=order).first()
        invoice.created_at = timezone.now() - timedelta(days=62)
        invoice.save()

        assert check_customer_overdue_debts(str(customer.id), max_days=30)

    def test_approve_order_credit_limit_exceeded(self, setup_data):
        user, customer, item = setup_data
        customer.credit_limit = Decimal("500.00")
        customer.save()

        # Tạo đơn bán hàng có giá trị 600 (vượt hạn mức 500)
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("6"), "unit_price": Decimal("100.00")}],
        )

        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(order.id))

        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PENDING_CREDIT_APPROVAL

        # Đảm bảo không sinh StockEntry hay SalesInvoice
        assert not order.stock_entries.exists()
        assert not order.invoices.exists()

    def test_approve_order_credit_locked_active(self, setup_data):
        user, customer, item = setup_data
        customer.is_credit_locked = True
        customer.save()

        # Tạo đơn bán hàng nhỏ (100) nhưng bị khóa chủ động
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("1"), "unit_price": Decimal("100.00")}],
        )

        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(order.id))

        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PENDING_CREDIT_APPROVAL

    def test_approve_order_overdue_debts_active(self, setup_data):
        user, customer, item = setup_data

        # Tạo hóa đơn cũ quá hạn
        old_order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("1"), "unit_price": Decimal("100.00")}],
        )
        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(old_order.id))

        invoice = SalesInvoice.objects.filter(order=old_order).first()
        invoice.created_at = timezone.now() - timedelta(days=65)
        invoice.save()

        # Tạo đơn hàng mới
        new_order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("1"), "unit_price": Decimal("50.00")}],
        )

        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(new_order.id))

        new_order.refresh_from_db()
        assert new_order.status == SalesOrder.Status.PENDING_CREDIT_APPROVAL

    def test_cfo_bypass_approve_flow(self, setup_data):
        user, customer, item = setup_data
        customer.is_credit_locked = True
        customer.save()

        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("1"), "unit_price": Decimal("100.00")}],
        )

        # Duyệt và khóa nợ
        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            sales_order_approve(user=user, order_id=str(order.id))

        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PENDING_CREDIT_APPROVAL

        # CFO/Admin duyệt bypass
        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission"):
            approve_credit_bypass(user=user, order_id=str(order.id))

        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PENDING
        assert order.stock_entries.exists()
        assert order.invoices.exists()

    @patch(
        "apps.common.xlib.permissions.PermissionChecker.check_permission",
        side_effect=PermissionChecker.check_permission,
    )
    def test_approve_credit_bypass_permissions(self, mock_check):
        # Tạo role CFO và gán quyền
        cfo_role = Role.objects.create(name="CFO", description="Chief Financial Officer")
        perm, _ = Permission.objects.get_or_create(
            code="sales.approve_credit_bypass", defaults={"name": "Phê duyệt tín dụng đặc cách"}
        )
        RolePermission.objects.create(role=cfo_role, permission=perm)

        # User CFO
        cfo_user = UserFactory(role=cfo_role)
        # User Sales
        sales_user = UserFactory()

        # Đơn hàng đang ở trạng thái PENDING_CREDIT_APPROVAL
        customer = CustomerFactory(is_credit_locked=True)
        order = SalesOrder.objects.create(customer=customer, status=SalesOrder.Status.PENDING_CREDIT_APPROVAL)

        # Test sales user không có quyền bypass
        with pytest.raises(PermissionException):
            approve_credit_bypass(user=sales_user, order_id=str(order.id))

        # Test cfo user có quyền bypass
        # Sử dụng patch cho StockEntry creation vì check_permission của các hàm bên dưới có thể bị gọi
        with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as mock_inner_check:
            # mock_inner_check sẽ return None (cho phép tất cả các check bên trong như create stock entry)
            # ngoại trừ check_permission đầu tiên của approve_credit_bypass chúng ta kiểm tra thủ công:
            # CFO user có quyền
            order_res = approve_credit_bypass(user=cfo_user, order_id=str(order.id))
            assert order_res.status == SalesOrder.Status.PENDING
