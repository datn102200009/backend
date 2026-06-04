from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.models import StockLedger
from apps.inventory.tests.factories import CustomerFactory, ItemFactory, UserFactory, WarehouseFactory
from apps.sales.models import SalesOrder
from apps.sales.services import sales_order_create, sales_order_delete, sales_order_update

pytestmark = pytest.mark.django_db


class TestSalesOrderServices:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        customer = CustomerFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()

        # Tạo tồn kho khả dụng để pass Validation
        StockLedger.objects.create(
            item=item,
            warehouse=warehouse,
            posting_date="2023-01-01",
            actual_quantity=Decimal("100.00"),
            voucher_number="TEST-IN",
            voucher_type="Stock In",
        )

        return user, customer, item, warehouse

    def test_sales_order_create(self, setup_data):
        user, customer, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        order = sales_order_create(user=user, customer_id=str(customer.id), lines=lines)

        assert order.id is not None
        assert order.status == SalesOrder.Status.DRAFT
        assert order.total_amount == Decimal("500.00")
        assert order.lines.count() == 1

    def test_sales_order_update(self, setup_data):
        user, customer, item, warehouse = setup_data

        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        updated_lines = [{"item_id": str(item.id), "quantity": Decimal("20.00"), "unit_price": Decimal("50.00")}]
        updated_order = sales_order_update(
            user=user,
            order_id=str(order.id),
            customer_id=str(customer.id),
            status=SalesOrder.Status.DRAFT,
            lines=updated_lines,
        )

        assert updated_order.status == SalesOrder.Status.DRAFT
        assert updated_order.total_amount == Decimal("1000.00")

    def test_sales_order_delete(self, setup_data):
        user, customer, item, warehouse = setup_data
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        sales_order_delete(user=user, order_id=str(order.id))

        assert not SalesOrder.objects.filter(id=order.id).exists()

    def test_sales_order_create_with_deposit_valid(self, setup_data):
        user, customer, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        order = sales_order_create(
            user=user, customer_id=str(customer.id), lines=lines, advance_paid_amount=Decimal("200.00")
        )

        assert order.advance_paid_amount == Decimal("200.00")
        assert order.total_amount == Decimal("500.00")

    def test_sales_order_create_with_deposit_invalid(self, setup_data):
        user, customer, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        with pytest.raises(ValidationException) as excinfo:
            sales_order_create(
                user=user, customer_id=str(customer.id), lines=lines, advance_paid_amount=Decimal("600.00")
            )
        assert "Số tiền cọc không được lớn hơn tổng giá trị đơn hàng" in str(excinfo.value)

    def test_sales_order_update_with_deposit_valid(self, setup_data):
        user, customer, item, warehouse = setup_data
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        updated_order = sales_order_update(
            user=user,
            order_id=str(order.id),
            customer_id=str(customer.id),
            status=SalesOrder.Status.DRAFT,
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("150.00"),
        )
        assert updated_order.advance_paid_amount == Decimal("150.00")

    def test_sales_order_update_with_deposit_invalid(self, setup_data):
        user, customer, item, warehouse = setup_data
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        with pytest.raises(ValidationException) as excinfo:
            sales_order_update(
                user=user,
                order_id=str(order.id),
                customer_id=str(customer.id),
                status=SalesOrder.Status.DRAFT,
                lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
                advance_paid_amount=Decimal("700.00"),
            )
        assert "Số tiền cọc không được lớn hơn tổng giá trị đơn hàng" in str(excinfo.value)

    def test_sales_order_delete_with_deposit(self, setup_data):
        user, customer, item, warehouse = setup_data
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )

        with pytest.raises(ValidationException) as excinfo:
            sales_order_delete(user=user, order_id=str(order.id))
        assert "Không thể xóa đơn hàng đã phát sinh thanh toán cọc" in str(excinfo.value)

    def test_sales_order_approve_creates_cash_flow(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.sales.services import sales_order_approve

        user, customer, item, warehouse = setup_data
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )

        # Make sure the customer credit is valid to allow direct approval (PENDING status)
        # In our factories.py, credit_limit might be low. We can set it to high.
        customer.credit_limit = Decimal("1000000.00")
        customer.save()

        approved_order = sales_order_approve(user=user, order_id=str(order.id))
        assert approved_order.status == SalesOrder.Status.PENDING

        # Check if cash flow transaction was created automatically
        cf = CashFlowTransaction.objects.filter(sales_order=approved_order).first()
        assert cf is not None
        assert cf.payment_type == "receive"
        assert cf.amount == Decimal("100.00")
        assert cf.category == "Đặt cọc đơn hàng"

        # Check idempotency
        cf_count = CashFlowTransaction.objects.filter(sales_order=approved_order).count()
        assert cf_count == 1

    def test_sales_order_cancel(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.inventory.models import StockEntry
        from apps.inventory.services import stock_entry_update, stock_issue_approve
        from apps.sales.models import SalesInvoice
        from apps.sales.services import sales_order_approve, sales_order_cancel

        user, customer, item, warehouse = setup_data
        customer.credit_limit = Decimal("1000000.00")
        customer.save()

        # 1. Create a SO with deposit
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )

        # 2. Approve SO -> creates draft stock entry, invoice, and deposit cash flow
        sales_order_approve(user=user, order_id=str(order.id))

        # Check that we have a draft stock entry
        stock_entry = StockEntry.objects.filter(sales_order=order, status="draft").first()
        assert stock_entry is not None

        # 3. Complete the stock entry (posted)
        # Update source warehouse first
        stock_entry_update(
            user=user,
            stock_entry_id=str(stock_entry.id),
            details=[
                {
                    "detail_id": str(stock_entry.details.first().id),
                    "source_warehouse_id": str(warehouse.id),
                    "quantity": Decimal("10.00"),
                }
            ],
        )
        stock_issue_approve(user=user, stock_entry_id=str(stock_entry.id))

        # 4. Pay remaining amount on invoice
        invoice = SalesInvoice.objects.filter(order=order).first()
        assert invoice is not None

        from apps.finance.services import cash_flow_create

        cash_flow_create(
            user=user,
            payment_type="receive",
            amount=Decimal("400.00"),
            payment_date="2026-06-03",
            sales_invoice_id=str(invoice.id),
            category="Thanh toán hóa đơn",
        )

        # Re-fetch order and invoice to verify states
        order.refresh_from_db()
        invoice.refresh_from_db()
        assert order.status == SalesOrder.Status.COMPLETED
        assert invoice.status == SalesInvoice.Status.PAID

        # 5. Cancel order
        sales_order_cancel(user=user, order_id=str(order.id))

        # 6. Verify cancellation effects
        order.refresh_from_db()
        invoice.refresh_from_db()

        assert order.status == SalesOrder.Status.CANCELLED
        assert order.advance_paid_amount == Decimal("0.00")
        assert invoice.status == SalesInvoice.Status.CANCELLED
        assert invoice.paid_amount == Decimal("0.00")

        # Verify that reversing stock entry is created and posted
        rev_stock_entry = StockEntry.objects.filter(sales_order=order, purpose="receipt").first()
        assert rev_stock_entry is not None
        assert rev_stock_entry.status == "posted"
        assert rev_stock_entry.details.first().target_warehouse == warehouse
        assert rev_stock_entry.details.first().quantity == Decimal("10.00")

        # Verify reversing cash flow transactions
        from django.db.models import Q

        txs = CashFlowTransaction.objects.filter(Q(sales_order=order) | Q(sales_invoice__order=order))
        reversals = txs.filter(category="Hoàn trả thanh toán")
        assert reversals.count() == 2
        assert set(reversals.values_list("amount", flat=True)) == {Decimal("100.00"), Decimal("400.00")}

    def test_sales_order_cancel_permission_check(self, setup_data, mock_permission_checker):
        from apps.sales.services import sales_order_cancel
        from apps.sales.tests.factories import SalesOrderFactory

        user, _, _, _ = setup_data
        order = SalesOrderFactory(status="pending")

        # Call the service which triggers the permission check
        try:
            sales_order_cancel(user=user, order_id=str(order.id))
        except Exception:
            pass  # We only care that check_permission was called

        mock_permission_checker.assert_called_with(user, "sales.cancel_order")
