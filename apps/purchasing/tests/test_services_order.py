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
            lines=updated_lines,
        )

        assert updated_order.status == PurchaseOrder.Status.DRAFT
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
        from apps.finance.services import cash_flow_approve
        from apps.inventory.models import StockEntry
        from apps.inventory.tests.factories import WarehouseFactory
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.services import (
            purchase_order_approve,
            purchase_order_cancel,
            shipment_complete,
            shipment_create_from_po,
            shipment_update,
        )

        user, vendor, item = setup_data
        warehouse = WarehouseFactory()

        # 1. Create a PO with deposit
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )

        # 2. Approve PO -> creates invoice and deposit cash flow (no stock entry yet)
        purchase_order_approve(user=user, order_id=str(order.id))

        # Approve deposit cash flow to credit PO and invoice
        cf_dep = CashFlowTransaction.objects.filter(purchase_order=order, payment_type="pay").first()
        cash_flow_approve(user=user, tx_id=str(cf_dep.id))

        # 3. Create shipment and complete it (posted stock entry)
        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-TEST-CANCEL-1",
            name="Shipment for cancel test",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        details = [
            {
                "po_line_id": str(order.lines.first().id),
                "item_id": str(item.id),
                "quantity": Decimal("10.00"),
                "target_warehouse_id": str(warehouse.id),
            }
        ]
        shipment_complete(
            user=user,
            shipment_id=str(shipment.id),
            details=details,
            total_logistic_fees=Decimal("0.00"),
        )

        # 4. Pay remaining amount on invoice
        invoice = PurchaseInvoice.objects.filter(order=order).first()
        assert invoice is not None

        from apps.finance.services import cash_flow_create

        tx = cash_flow_create(
            user=user,
            payment_type="pay",
            amount=Decimal("400.00"),
            payment_date="2026-06-03",
            purchase_invoice_id=str(invoice.id),
            category="Thanh toán hóa đơn",
        )
        cash_flow_approve(user=user, tx_id=str(tx.id))

        # Re-fetch order and invoice to verify states
        order.refresh_from_db()
        invoice.refresh_from_db()
        assert order.status == PurchaseOrder.Status.COMPLETED
        assert invoice.status == PurchaseInvoice.Status.PAID

        # 5. Cancel order -> transitions to CANCEL_PENDING due to existing cash flows
        purchase_order_cancel(user=user, order_id=str(order.id))

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCEL_PENDING

        # Approve reversal cash flows to finalize cancellation
        reversals = CashFlowTransaction.objects.filter(purchase_order=order, category="Hoàn trả thanh toán")
        assert reversals.count() == 2
        for r_cf in reversals:
            cash_flow_approve(user=user, tx_id=str(r_cf.id))

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

    def test_purchase_order_cancel_no_goods_refund_deposit(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.finance.services import cash_flow_approve
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.services import purchase_order_approve, purchase_order_cancel

        user, vendor, item = setup_data

        # Create PO with deposit
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )
        purchase_order_approve(user=user, order_id=str(order.id))

        cf_dep = CashFlowTransaction.objects.filter(purchase_order=order, payment_type="pay").first()
        cash_flow_approve(user=user, tx_id=str(cf_dep.id))

        # Cancel with refund_deposit=True -> transitions to CANCEL_PENDING
        purchase_order_cancel(user=user, order_id=str(order.id), refund_deposit=True)

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCEL_PENDING

        cf_rev = CashFlowTransaction.objects.filter(purchase_order=order, category="Hoàn trả thanh toán").first()
        assert cf_rev is not None
        cash_flow_approve(user=user, tx_id=str(cf_rev.id))

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED
        assert order.advance_paid_amount == Decimal("0.00")

        # Check that invoice is cancelled and paid_amount is 0
        invoice = PurchaseInvoice.objects.filter(order=order).first()
        assert invoice.status == PurchaseInvoice.Status.CANCELLED
        assert invoice.paid_amount == Decimal("0.00")

    def test_purchase_order_cancel_no_goods_keep_deposit(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.finance.services import cash_flow_approve
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.services import purchase_order_approve, purchase_order_cancel

        user, vendor, item = setup_data

        # Create PO with deposit
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("100.00"),
        )
        purchase_order_approve(user=user, order_id=str(order.id))

        cf_dep = CashFlowTransaction.objects.filter(purchase_order=order, payment_type="pay").first()
        cash_flow_approve(user=user, tx_id=str(cf_dep.id))

        # Cancel with refund_deposit=False -> transitions straight to CANCELLED since no new cash flows are created
        purchase_order_cancel(user=user, order_id=str(order.id), refund_deposit=False)

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED
        # Keep deposit: advance_paid_amount remains
        assert order.advance_paid_amount == Decimal("100.00")

        invoice = PurchaseInvoice.objects.filter(order=order).first()
        assert invoice.status == PurchaseInvoice.Status.CANCELLED
        assert invoice.paid_amount == Decimal("100.00")

        # Check NO reversing cash flow was created
        assert not CashFlowTransaction.objects.filter(purchase_order=order, category="Hoàn trả thanh toán").exists()

    def test_purchase_order_cancel_with_goods_keep_goods_diff_positive(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.finance.services import cash_flow_approve
        from apps.inventory.tests.factories import WarehouseFactory
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.services import (
            purchase_order_approve,
            purchase_order_cancel,
            shipment_complete,
            shipment_create_from_po,
            shipment_update,
        )

        user, vendor, item = setup_data
        warehouse = WarehouseFactory()

        # Create PO: Total 500, Deposit 200
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("200.00"),
        )
        purchase_order_approve(user=user, order_id=str(order.id))

        cf_dep = CashFlowTransaction.objects.filter(purchase_order=order, payment_type="pay").first()
        cash_flow_approve(user=user, tx_id=str(cf_dep.id))

        # Receive 6 items (received value = 6 * 50 = 300) via shipment
        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-TEST-CANCEL-2",
            name="Shipment for cancel positive diff",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        details = [
            {
                "po_line_id": str(order.lines.first().id),
                "item_id": str(item.id),
                "quantity": Decimal("6.00"),
                "target_warehouse_id": str(warehouse.id),
            }
        ]
        shipment_complete(
            user=user,
            shipment_id=str(shipment.id),
            details=details,
            total_logistic_fees=Decimal("0.00"),
        )

        # Re-fetch state: received_value=300, total_paid=200. diff = 300 - 200 = 100 > 0.
        # Cancel with keep_goods=True -> transitions to CANCEL_PENDING
        purchase_order_cancel(user=user, order_id=str(order.id), keep_goods=True)

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCEL_PENDING

        cf_diff = CashFlowTransaction.objects.filter(
            purchase_order=order, category="Thanh toán đối ứng chênh lệch hủy đơn"
        ).first()
        assert cf_diff is not None
        assert cf_diff.amount == Decimal("100.00")
        assert cf_diff.payment_type == "pay"

        cash_flow_approve(user=user, tx_id=str(cf_diff.id))

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED
        # Balanced advance_paid_amount becomes equal to received_value (300)
        assert order.advance_paid_amount == Decimal("300.00")

        # Check stock entries (original is posted, no new issue reversals)
        assert order.stock_entries.filter(status="posted").count() == 1
        assert not order.stock_entries.filter(purpose="issue").exists()

        # Check rates
        assert order.receipt_fulfillment_rate == Decimal("60.00")
        assert order.payment_fulfillment_rate == Decimal("60.00")

    def test_purchase_order_cancel_with_goods_keep_goods_diff_negative(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.finance.services import cash_flow_approve
        from apps.inventory.tests.factories import WarehouseFactory
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.services import (
            purchase_order_approve,
            purchase_order_cancel,
            shipment_complete,
            shipment_create_from_po,
            shipment_update,
        )

        user, vendor, item = setup_data
        warehouse = WarehouseFactory()

        # Create PO: Total 500, Deposit 400
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("400.00"),
        )
        purchase_order_approve(user=user, order_id=str(order.id))

        cf_dep = CashFlowTransaction.objects.filter(purchase_order=order, payment_type="pay").first()
        cash_flow_approve(user=user, tx_id=str(cf_dep.id))

        # Receive 6 items (received value = 6 * 50 = 300)
        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-TEST-CANCEL-3",
            name="Shipment for cancel negative diff",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        details = [
            {
                "po_line_id": str(order.lines.first().id),
                "item_id": str(item.id),
                "quantity": Decimal("6.00"),
                "target_warehouse_id": str(warehouse.id),
            }
        ]
        shipment_complete(
            user=user,
            shipment_id=str(shipment.id),
            details=details,
            total_logistic_fees=Decimal("0.00"),
        )

        # Re-fetch state: received_value=300, total_paid=400. diff = 300 - 400 = -100 < 0.
        # Cancel with keep_goods=True -> transitions to CANCEL_PENDING
        purchase_order_cancel(user=user, order_id=str(order.id), keep_goods=True)

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCEL_PENDING

        cf_diff = CashFlowTransaction.objects.filter(
            purchase_order=order, category="Hoàn trả đối ứng chênh lệch hủy đơn"
        ).first()
        assert cf_diff is not None
        assert cf_diff.amount == Decimal("100.00")
        assert cf_diff.payment_type == "receive"

        cash_flow_approve(user=user, tx_id=str(cf_diff.id))

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED
        # Balanced advance_paid_amount becomes equal to received_value (300)
        assert order.advance_paid_amount == Decimal("300.00")

        # Check rates
        assert order.receipt_fulfillment_rate == Decimal("60.00")
        assert order.payment_fulfillment_rate == Decimal("60.00")

    def test_purchase_order_cancel_with_goods_reverse_all(self, setup_data):
        from apps.finance.models import CashFlowTransaction
        from apps.finance.services import cash_flow_approve
        from apps.inventory.models import StockEntry
        from apps.inventory.tests.factories import WarehouseFactory
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.services import (
            purchase_order_approve,
            purchase_order_cancel,
            shipment_complete,
            shipment_create_from_po,
            shipment_update,
        )

        user, vendor, item = setup_data
        warehouse = WarehouseFactory()

        # Create PO: Total 500, Deposit 200
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
            advance_paid_amount=Decimal("200.00"),
        )
        purchase_order_approve(user=user, order_id=str(order.id))

        cf_dep = CashFlowTransaction.objects.filter(purchase_order=order, payment_type="pay").first()
        cash_flow_approve(user=user, tx_id=str(cf_dep.id))

        # Receive 6 items (received value = 6 * 50 = 300)
        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-TEST-CANCEL-4",
            name="Shipment for cancel reverse all",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        details = [
            {
                "po_line_id": str(order.lines.first().id),
                "item_id": str(item.id),
                "quantity": Decimal("6.00"),
                "target_warehouse_id": str(warehouse.id),
            }
        ]
        shipment_complete(
            user=user,
            shipment_id=str(shipment.id),
            details=details,
            total_logistic_fees=Decimal("0.00"),
        )

        # Cancel with keep_goods=False (Default/Reverse all) -> transitions to CANCEL_PENDING
        purchase_order_cancel(user=user, order_id=str(order.id), keep_goods=False)

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCEL_PENDING

        cf_rev = CashFlowTransaction.objects.filter(purchase_order=order, category="Hoàn trả thanh toán").first()
        assert cf_rev is not None
        assert cf_rev.amount == Decimal("200.00")
        assert cf_rev.payment_type == "receive"

        cash_flow_approve(user=user, tx_id=str(cf_rev.id))

        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED
        # All money returned, so advance_paid_amount is 0
        assert order.advance_paid_amount == Decimal("0.00")

        # Check reversing stock entry of purpose 'issue' is posted
        rev_stock = StockEntry.objects.filter(purchase_order=order, purpose="issue").first()
        assert rev_stock is not None
        assert rev_stock.status == "posted"

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

    def test_purchase_order_approve_log_no_stock_entry_id(self, setup_data):
        """Log approve KHÔNG chứa stock_entry_id vì không còn tạo StockEntry nháp."""
        from apps.accounts.models import SystemLog
        from apps.purchasing.services import purchase_order_approve

        user, vendor, item = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        purchase_order_approve(user=user, order_id=str(order.id))
        log = SystemLog.objects.filter(table_name="purchase_order", record_id=str(order.id), action="approve").first()
        assert log is not None
        assert "stock_entry_id" not in log.new_value
        assert log.new_value.get("invoice_id") is not None
