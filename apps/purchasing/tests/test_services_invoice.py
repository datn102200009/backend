from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.models import StockEntry
from apps.inventory.services import stock_entry_update, stock_in_approve
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory, WarehouseFactory
from apps.purchasing.models import PurchaseInvoice, PurchaseOrder
from apps.purchasing.services import purchase_order_approve, purchase_order_create

pytestmark = pytest.mark.django_db


class TestPurchaseInvoiceServices:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        vendor = SupplierFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()
        return user, vendor, item, warehouse

    def test_purchase_order_approve_workflow(self, setup_data):
        user, vendor, item, warehouse = setup_data

        # 1. Create order
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)

        # 2. Approve order
        order = purchase_order_approve(user=user, order_id=str(order.id))

        assert order.status == PurchaseOrder.Status.PENDING

        invoice = order.invoices.first()
        assert invoice is not None
        assert invoice.status == PurchaseInvoice.Status.UNPAID
        assert invoice.total_amount == Decimal("500.00")

        stock_entry = order.stock_entries.first()
        assert stock_entry is not None
        assert stock_entry.status == "draft"

        # 3. Verify stock detail warehouse is None initially
        detail = stock_entry.details.first()
        assert detail.target_warehouse is None

        # 4. Warehouse staff updates warehouse
        stock_entry_update(
            user=user,
            stock_entry_id=str(stock_entry.id),
            details=[{"detail_id": str(detail.id), "target_warehouse_id": str(warehouse.id)}],
        )
        detail.refresh_from_db()
        assert detail.target_warehouse == warehouse

        # 5. Approve stock entry
        stock_in_approve(user=user, stock_entry_id=str(stock_entry.id))

        # 6. Verify order status becomes SHIPPED_UNPAID
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.SHIPPED_UNPAID

    def test_purchase_order_approve_already_approved(self, setup_data):
        user, vendor, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)

        purchase_order_approve(user=user, order_id=str(order.id))

        with pytest.raises(ValidationException):
            purchase_order_approve(user=user, order_id=str(order.id))
