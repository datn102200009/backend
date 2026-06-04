from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory
from apps.purchasing.models import PurchaseOrder
from apps.purchasing.services import purchase_order_create, purchase_order_delete, purchase_order_update

pytestmark = pytest.mark.django_db


class TestPurchaseOrderServices:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        vendor = SupplierFactory()
        item = ItemFactory()
        return user, vendor, item

    def test_purchase_order_create(self, setup_data):
        user, vendor, item = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)

        assert order.id is not None
        assert order.status == PurchaseOrder.Status.DRAFT
        assert order.total_amount == Decimal("500.00")
        assert order.lines.count() == 1

    def test_purchase_order_update(self, setup_data):
        user, vendor, item = setup_data

        # Create initially
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        # Update
        updated_lines = [{"item_id": str(item.id), "quantity": Decimal("20.00"), "unit_price": Decimal("50.00")}]
        updated_order = purchase_order_update(
            user=user,
            order_id=str(order.id),
            vendor_id=str(vendor.id),
            status=PurchaseOrder.Status.PENDING,
            lines=updated_lines,
        )

        assert updated_order.status == PurchaseOrder.Status.PENDING
        assert updated_order.total_amount == Decimal("1000.00")

    def test_purchase_order_update_invalid_status(self, setup_data):
        user, vendor, item = setup_data
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=[])

        # Mock status to COMPLETED
        order.status = PurchaseOrder.Status.COMPLETED
        order.save()

        with pytest.raises(ValidationException):
            purchase_order_update(
                user=user,
                order_id=str(order.id),
                vendor_id=str(vendor.id),
                status=PurchaseOrder.Status.PENDING,
                lines=[],
            )

    def test_purchase_order_delete(self, setup_data):
        user, vendor, item = setup_data
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=[])

        purchase_order_delete(user=user, order_id=str(order.id))

        assert not PurchaseOrder.objects.filter(id=order.id).exists()

    def test_purchase_order_create_with_deposit_valid(self, setup_data):
        user, vendor, item = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        order = purchase_order_create(
            user=user, vendor_id=str(vendor.id), lines=lines, advance_paid_amount=Decimal("200.00")
        )

        assert order.advance_paid_amount == Decimal("200.00")
        assert order.total_amount == Decimal("500.00")

    def test_purchase_order_create_with_deposit_invalid(self, setup_data):
        user, vendor, item = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        with pytest.raises(ValidationException) as excinfo:
            purchase_order_create(
                user=user, vendor_id=str(vendor.id), lines=lines, advance_paid_amount=Decimal("600.00")
            )
        assert "Số tiền cọc không được lớn hơn tổng giá trị đơn hàng" in str(excinfo.value)

    def test_purchase_order_update_with_deposit_valid(self, setup_data):
        user, vendor, item = setup_data
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        updated_order = purchase_order_update(
            user=user,
            order_id=str(order.id),
            vendor_id=str(vendor.id),
            status=PurchaseOrder.Status.DRAFT,
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("150.00"),
        )
        assert updated_order.advance_paid_amount == Decimal("150.00")

    def test_purchase_order_update_with_deposit_invalid(self, setup_data):
        user, vendor, item = setup_data
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        with pytest.raises(ValidationException) as excinfo:
            purchase_order_update(
                user=user,
                order_id=str(order.id),
                vendor_id=str(vendor.id),
                status=PurchaseOrder.Status.DRAFT,
                lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
                advance_paid_amount=Decimal("700.00"),
            )
        assert "Số tiền cọc không được lớn hơn tổng giá trị đơn hàng" in str(excinfo.value)

    def test_purchase_order_delete_with_deposit(self, setup_data):
        user, vendor, item = setup_data
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )

        with pytest.raises(ValidationException) as excinfo:
            purchase_order_delete(user=user, order_id=str(order.id))
        assert "Không thể xóa đơn hàng đã phát sinh thanh toán cọc" in str(excinfo.value)

    def test_purchase_order_approve_creates_cash_flow(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.purchasing.services import purchase_order_approve

        user, vendor, item = setup_data
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )

        approved_order = purchase_order_approve(user=user, order_id=str(order.id))
        assert approved_order.status == PurchaseOrder.Status.PENDING

        # Check if cash flow transaction was created automatically
        cf = CashFlowTransaction.objects.filter(purchase_order=approved_order).first()
        assert cf is not None
        assert cf.payment_type == "pay"
        assert cf.amount == Decimal("100.00")
        assert cf.category == "Đặt cọc đơn hàng"

        # Check idempotency
        # Try calling approve again or verify no duplicate transaction exists
        cf_count = CashFlowTransaction.objects.filter(purchase_order=approved_order).count()
        assert cf_count == 1

    def test_purchase_order_cancel(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.inventory.models import StockEntry
        from apps.inventory.services import stock_entry_update, stock_in_approve
        from apps.inventory.tests.factories import WarehouseFactory
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.services import purchase_order_approve, purchase_order_cancel

        user, vendor, item = setup_data
        warehouse = WarehouseFactory()

        # 1. Create a PO with deposit
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )

        # 2. Approve PO -> creates draft stock entry, invoice, and deposit cash flow
        purchase_order_approve(user=user, order_id=str(order.id))

        # Check that we have a draft stock entry
        stock_entry = StockEntry.objects.filter(purchase_order=order, status="draft").first()
        assert stock_entry is not None

        # 3. Complete the stock entry (posted)
        # Update target warehouse first
        stock_entry_update(
            user=user,
            stock_entry_id=str(stock_entry.id),
            details=[
                {
                    "detail_id": str(stock_entry.details.first().id),
                    "target_warehouse_id": str(warehouse.id),
                    "quantity": Decimal("10.00"),
                }
            ],
        )
        stock_in_approve(user=user, stock_entry_id=str(stock_entry.id))

        # 4. Pay remaining amount on invoice
        invoice = PurchaseInvoice.objects.filter(order=order).first()
        assert invoice is not None

        from apps.finance.services import cash_flow_create

        cash_flow_create(
            user=user,
            payment_type="pay",
            amount=Decimal("400.00"),
            payment_date="2026-06-03",
            purchase_invoice_id=str(invoice.id),
            category="Thanh toán hóa đơn",
        )

        # Re-fetch order and invoice to verify states
        order.refresh_from_db()
        invoice.refresh_from_db()
        assert order.status == PurchaseOrder.Status.COMPLETED
        assert invoice.status == PurchaseInvoice.Status.PAID

        # 5. Cancel order
        purchase_order_cancel(user=user, order_id=str(order.id))

        # 6. Verify cancellation effects
        order.refresh_from_db()
        invoice.refresh_from_db()

        assert order.status == PurchaseOrder.Status.CANCELLED
        assert order.advance_paid_amount == Decimal("0.00")
        assert invoice.status == PurchaseInvoice.Status.CANCELLED
        assert invoice.paid_amount == Decimal("0.00")

        # Verify that reversing stock entry is created and posted
        rev_stock_entry = StockEntry.objects.filter(purchase_order=order, purpose="issue").first()
        assert rev_stock_entry is not None
        assert rev_stock_entry.status == "posted"
        assert rev_stock_entry.details.first().source_warehouse == warehouse
        assert rev_stock_entry.details.first().quantity == Decimal("10.00")

        # Verify reversing cash flow transactions
        from django.db.models import Q

        txs = CashFlowTransaction.objects.filter(Q(purchase_order=order) | Q(purchase_invoice__order=order))
        reversals = txs.filter(category="Hoàn trả thanh toán")
        assert reversals.count() == 2
        assert set(reversals.values_list("amount", flat=True)) == {Decimal("100.00"), Decimal("400.00")}

    def test_purchase_order_cancel_permission_check(self, setup_data, mock_permission_checker):
        from apps.purchasing.services import purchase_order_cancel
        from apps.purchasing.tests.factories import PurchaseOrderFactory

        user, _, _ = setup_data
        order = PurchaseOrderFactory(status="pending")

        # Call the service which triggers the permission check
        try:
            purchase_order_cancel(user=user, order_id=str(order.id))
        except Exception:
            pass  # We only care that check_permission was called

        mock_permission_checker.assert_called_with(user, "purchasing.cancel_order")
