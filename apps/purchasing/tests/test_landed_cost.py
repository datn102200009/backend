from decimal import Decimal

import pytest

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory, WarehouseFactory
from apps.purchasing.models import Shipment
from apps.purchasing.services import (
    purchase_order_approve,
    purchase_order_create,
    record_shipment_logistic_fees,
    shipment_create,
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

    def test_shipment_create_and_link_stock_entries(self, setup_data):
        user, vendor, item, warehouse = setup_data

        # Create PO and approve to generate stock entry
        lines = [{"item_id": str(item.id), "quantity": Decimal("5.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        stock_entry = order.stock_entries.first()
        assert stock_entry is not None

        # Create shipment linking this stock entry
        shipment = shipment_create(
            user=user,
            shipment_num="SH-TEST-001",
            name="Imported goods batch 1",
            remarks="Fast delivery",
            stock_entry_ids=[str(stock_entry.id)],
        )

        assert shipment.shipment_num == "SH-TEST-001"
        assert shipment.status == "draft"
        assert shipment.total_logistic_fees == Decimal("0.00")

        # Verify relation
        stock_entry.refresh_from_db()
        assert stock_entry.shipment == shipment

    def test_record_shipment_logistic_fees(self, setup_data):
        user, vendor, item, warehouse = setup_data

        shipment = shipment_create(
            user=user,
            shipment_num="SH-TEST-002",
            name="Logistic fees test shipment",
        )

        # Allocate fees
        updated_shipment = record_shipment_logistic_fees(
            user=user,
            shipment_id=str(shipment.id),
            total_logistic_fees=Decimal("1500000.00"),
        )

        assert updated_shipment.status == "completed"
        assert updated_shipment.total_logistic_fees == Decimal("1500000.00")

    def test_record_shipment_logistic_fees_validation(self, setup_data):
        user, vendor, item, warehouse = setup_data

        shipment = shipment_create(
            user=user,
            shipment_num="SH-TEST-003",
            name="Validation check",
        )

        # Try to allocate negative or zero fee
        with pytest.raises(ValidationException):
            record_shipment_logistic_fees(
                user=user,
                shipment_id=str(shipment.id),
                total_logistic_fees=Decimal("0.00"),
            )

        with pytest.raises(ValidationException):
            record_shipment_logistic_fees(
                user=user,
                shipment_id=str(shipment.id),
                total_logistic_fees=Decimal("-50.00"),
            )
