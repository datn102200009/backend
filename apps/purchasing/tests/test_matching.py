from decimal import Decimal

import pytest

from apps.common.xlib.exceptions import NotFoundException
from apps.finance.models import TechnicalCertification
from apps.inventory.models import StockEntry
from apps.inventory.services import stock_entry_update, stock_in_approve
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory, WarehouseFactory
from apps.purchasing.models import PurchaseInvoice, PurchaseOrder
from apps.purchasing.services import purchase_order_approve, purchase_order_create, verify_4_way_matching

pytestmark = pytest.mark.django_db


class TestFourWayMatching:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        vendor = SupplierFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()
        return user, vendor, item, warehouse

    def test_matching_success(self, setup_data):
        user, vendor, item, warehouse = setup_data

        # 1. Create and Approve Order
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        invoice = order.invoices.first()
        stock_entry = order.stock_entries.first()

        # Update and Approve Stock Entry (receipt)
        detail = stock_entry.details.first()
        stock_entry_update(
            user=user,
            stock_entry_id=str(stock_entry.id),
            details=[{"detail_id": str(detail.id), "target_warehouse_id": str(warehouse.id)}],
        )

        # Verify will be automatically run inside stock_in_approve
        stock_in_approve(user=user, stock_entry_id=str(stock_entry.id))

        invoice.refresh_from_db()
        assert invoice.status == PurchaseInvoice.Status.UNPAID
        assert invoice.qty_fulfillment_rate == Decimal("100.00")
        assert invoice.block_reason is None

    def test_matching_unit_price_mismatch_blocks_payment(self, setup_data):
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        invoice = order.invoices.first()

        # Manually alter unit price in invoice line to create mismatch
        inv_line = invoice.lines.first()
        inv_line.unit_price = Decimal("55.00")
        inv_line.save()

        # Run matching
        verify_4_way_matching(invoice_id=str(invoice.id))

        invoice.refresh_from_db()
        # Mismatch does NOT block payment, status remains unpaid
        assert invoice.status == PurchaseInvoice.Status.UNPAID
        assert "Chênh lệch đơn giá" in invoice.block_reason

    def test_matching_qa_failure_blocks_payment(self, setup_data):
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        invoice = order.invoices.first()
        stock_entry = order.stock_entries.first()

        # Update and Approve Stock Entry
        detail = stock_entry.details.first()
        stock_entry_update(
            user=user,
            stock_entry_id=str(stock_entry.id),
            details=[{"detail_id": str(detail.id), "target_warehouse_id": str(warehouse.id)}],
        )

        # Create a FAILED Technical Certification for this item
        TechnicalCertification.objects.create(
            cert_id="CERT-FAIL-1",
            item=item,
            stock_entry=stock_entry,
            cert_type="QA-Check",
            result="FAILED",
        )

        # Approve Stock Entry (will trigger matching but NOT block it)
        stock_in_approve(user=user, stock_entry_id=str(stock_entry.id))

        invoice.refresh_from_db()
        # QA check failure does NOT block payment, status remains unpaid
        assert invoice.status == PurchaseInvoice.Status.UNPAID
        assert "không đạt kiểm định chất lượng" in invoice.block_reason

    def test_matching_quantity_discrepancy_calculated_correctly(self, setup_data):
        user, vendor, item, warehouse = setup_data

        # 1. Create order for 10 units
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        invoice = order.invoices.first()
        stock_entry = order.stock_entries.first()

        # 2. Modify received quantity in stock entry detail to 9 units (90%)
        detail = stock_entry.details.first()
        stock_entry_update(
            user=user,
            stock_entry_id=str(stock_entry.id),
            details=[
                {"detail_id": str(detail.id), "target_warehouse_id": str(warehouse.id), "quantity": Decimal("9.00")}
            ],
        )

        # Approve stock in
        stock_in_approve(user=user, stock_entry_id=str(stock_entry.id))

        invoice.refresh_from_db()
        # Qty mismatch does NOT block payment, status remains unpaid
        assert invoice.status == PurchaseInvoice.Status.UNPAID
        assert invoice.qty_fulfillment_rate == Decimal("90.00")

        # Verify line level qty_fulfillment_rate
        line = invoice.lines.first()
        assert line.qty_fulfillment_rate == Decimal("90.00")
