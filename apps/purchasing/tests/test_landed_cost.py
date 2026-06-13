from decimal import Decimal

import pytest

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory, WarehouseFactory
from apps.purchasing.models import Shipment
from apps.purchasing.services import (
    purchase_order_approve,
    purchase_order_create,
    shipment_complete,
    shipment_create_from_po,
    shipment_update,
)

pytestmark = pytest.mark.django_db


class TestLandedCost:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        vendor = SupplierFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()
        return user, vendor, item, warehouse

    def test_shipment_create_from_po_success(self, setup_data):
        user, vendor, item, warehouse = setup_data

        # Create PO and approve
        lines = [{"item_id": str(item.id), "quantity": Decimal("5.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        # Create shipment linking this PO
        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-TEST-001",
            name="Imported goods batch 1",
            remarks="Fast delivery",
            purchase_order_id=str(order.id),
        )

        assert shipment.shipment_num == "SH-TEST-001"
        assert shipment.status == Shipment.Status.DRAFT
        assert shipment.total_logistic_fees == Decimal("0.00")
        assert shipment.purchase_order == order

    def test_shipment_complete_success_with_fees(self, setup_data):
        user, vendor, item, warehouse = setup_data

        # Create PO and approve
        lines = [{"item_id": str(item.id), "quantity": Decimal("5.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        # Create shipment and update status to inspecting
        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-TEST-002",
            name="Landed cost complete test",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        # Complete shipment with logistic fees
        details = [
            {
                "po_line_id": str(order.lines.first().id),
                "item_id": str(item.id),
                "quantity": Decimal("5.00"),
                "target_warehouse_id": str(warehouse.id),
            }
        ]
        updated_shipment = shipment_complete(
            user=user,
            shipment_id=str(shipment.id),
            details=details,
            total_logistic_fees=Decimal("1500000.00"),
        )

        assert updated_shipment.status == Shipment.Status.COMPLETED
        assert updated_shipment.total_logistic_fees == Decimal("1500000.00")

        # Check posted StockEntry
        stock_entry = order.stock_entries.first()
        assert stock_entry is not None
        assert stock_entry.status == "posted"
        assert stock_entry.details.first().quantity == Decimal("5.00")

        # Check CashFlowTransaction for logistics fee
        from apps.finance.models import CashFlowTransaction

        cf = CashFlowTransaction.objects.filter(purchase_order=order, category="Chi phí vận chuyển lô hàng").first()
        assert cf is not None
        assert cf.amount == Decimal("1500000.00")

    def test_shipment_complete_validation_negative_fees(self, setup_data):
        user, vendor, item, warehouse = setup_data

        # Create PO and approve
        lines = [{"item_id": str(item.id), "quantity": Decimal("5.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-TEST-003",
            name="Validation check negative fees",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        details = [
            {
                "po_line_id": str(order.lines.first().id),
                "item_id": str(item.id),
                "quantity": Decimal("5.00"),
                "target_warehouse_id": str(warehouse.id),
            }
        ]

        # Try to complete with negative fees
        with pytest.raises(ValidationException):
            shipment_complete(
                user=user,
                shipment_id=str(shipment.id),
                details=details,
                total_logistic_fees=Decimal("-50.00"),
            )
