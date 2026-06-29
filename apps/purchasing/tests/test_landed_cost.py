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

        assert updated_shipment.status == Shipment.Status.PENDING_APPROVAL
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

        # Test approving cashflow transitions shipment to COMPLETED
        from apps.finance.services import cash_flow_approve

        cash_flow_approve(user=user, tx_id=str(cf.id))
        updated_shipment.refresh_from_db()
        assert updated_shipment.status == Shipment.Status.COMPLETED

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

    def test_shipment_complete_cumulative_exceed_po_quantity(self, setup_data):
        """Tổng lũy kế nhiều shipment KHÔNG được vượt SL đặt."""
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("5.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        # Shipment 1: nhập 3/5
        s1 = shipment_create_from_po(
            user=user,
            shipment_num="SH-CUM-1",
            name="cumulative 1",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(s1.id), status="inspecting")
        shipment_complete(
            user=user,
            shipment_id=str(s1.id),
            details=[
                {
                    "po_line_id": str(order.lines.first().id),
                    "item_id": str(item.id),
                    "quantity": Decimal("3.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
            total_logistic_fees=Decimal("0"),
        )

        # Shipment 2: thử nhập 3/5 nữa → tổng 6 > 5 → phải lỗi
        s2 = shipment_create_from_po(
            user=user,
            shipment_num="SH-CUM-2",
            name="cumulative 2",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(s2.id), status="inspecting")
        with pytest.raises(ValidationException) as excinfo:
            shipment_complete(
                user=user,
                shipment_id=str(s2.id),
                details=[
                    {
                        "po_line_id": str(order.lines.first().id),
                        "item_id": str(item.id),
                        "quantity": Decimal("3.00"),
                        "target_warehouse_id": str(warehouse.id),
                    }
                ],
                total_logistic_fees=Decimal("0"),
            )
        assert "vượt quá SL đặt" in str(excinfo.value)

    def test_shipment_complete_partial_acceptance_remaining(self, setup_data):
        """Nhập 3/5 đợt 1, 2/5 đợt 2: tổng = 5, KHÔNG lỗi."""
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("5.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        s1 = shipment_create_from_po(
            user=user,
            shipment_num="SH-PART-1",
            name="partial 1",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(s1.id), status="inspecting")
        shipment_complete(
            user=user,
            shipment_id=str(s1.id),
            details=[
                {
                    "po_line_id": str(order.lines.first().id),
                    "item_id": str(item.id),
                    "quantity": Decimal("3.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
            total_logistic_fees=Decimal("0"),
        )

        s2 = shipment_create_from_po(
            user=user,
            shipment_num="SH-PART-2",
            name="partial 2",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(s2.id), status="inspecting")
        updated = shipment_complete(
            user=user,
            shipment_id=str(s2.id),
            details=[
                {
                    "po_line_id": str(order.lines.first().id),
                    "item_id": str(item.id),
                    "quantity": Decimal("2.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
            total_logistic_fees=Decimal("0"),
        )
        assert updated.status == Shipment.Status.COMPLETED

    def test_shipment_complete_emits_log(self, setup_data, caplog):
        """Kiểm tra log được sinh ra khi hoàn tất lô hàng."""
        import logging

        user, vendor, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("5.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))
        s = shipment_create_from_po(
            user=user,
            shipment_num="SH-LOG-1",
            name="log test",
            purchase_order_id=str(order.id),
        )
        shipment_update(user=user, shipment_id=str(s.id), status="inspecting")

        with caplog.at_level(logging.INFO, logger="apps.purchasing.services"):
            shipment_complete(
                user=user,
                shipment_id=str(s.id),
                details=[
                    {
                        "po_line_id": str(order.lines.first().id),
                        "item_id": str(item.id),
                        "quantity": Decimal("5.00"),
                        "target_warehouse_id": str(warehouse.id),
                    }
                ],
                total_logistic_fees=Decimal("0"),
            )

        messages = [r.message for r in caplog.records]
        assert any("shipment_complete: start" in m for m in messages)
        assert any("created StockEntry" in m for m in messages)
        assert any("completed/submitted shipment_id" in m for m in messages)

    def test_shipment_serializer_remaining_quantity_after_other_shipment(self, setup_data):
        """Số lượng còn lại phải trừ đi lượng đã nhận ở shipment trước."""
        user, vendor, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("600.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        # Shipment 1: nhập 400
        s1 = shipment_create_from_po(user=user, shipment_num="SH-RM-1", name="r1", purchase_order_id=str(order.id))
        shipment_update(user=user, shipment_id=str(s1.id), status="inspecting")
        shipment_complete(
            user=user,
            shipment_id=str(s1.id),
            details=[
                {
                    "po_line_id": str(order.lines.first().id),
                    "item_id": str(item.id),
                    "quantity": Decimal("400.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
            total_logistic_fees=Decimal("0"),
        )

        # Tạo shipment 2 và check remaining_quantity qua serializer
        s2 = shipment_create_from_po(user=user, shipment_num="SH-RM-2", name="r2", purchase_order_id=str(order.id))
        from apps.purchasing.api.v1.serializers import ShipmentSerializer

        data = ShipmentSerializer(s2).data
        line_data = next(
            line_item for line_item in data["purchase_order_lines"] if line_item["item_id"] == str(item.id)
        )
        assert Decimal(line_data["quantity"]) == Decimal("600.00")  # tổng đặt
        assert Decimal(line_data["remaining_quantity"]) == Decimal("200.00")  # còn lại
        assert Decimal(line_data["received_quantity"]) == Decimal("400.00")  # đã nhận

    def test_shipment_serializer_remaining_quantity_zero_when_completed(self, setup_data):
        """Khi đã nhận đủ → remaining_quantity = 0."""
        user, vendor, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("600.00"), "unit_price": Decimal("100.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        # Shipment 1: nhập 400
        s1 = shipment_create_from_po(user=user, shipment_num="SH-RM-1", name="r1", purchase_order_id=str(order.id))
        shipment_update(user=user, shipment_id=str(s1.id), status="inspecting")
        shipment_complete(
            user=user,
            shipment_id=str(s1.id),
            details=[
                {
                    "po_line_id": str(order.lines.first().id),
                    "item_id": str(item.id),
                    "quantity": Decimal("400.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
            total_logistic_fees=Decimal("0"),
        )

        # Tạo shipment 2: nhập nốt 200
        s2 = shipment_create_from_po(user=user, shipment_num="SH-RM-2", name="r2", purchase_order_id=str(order.id))
        shipment_update(user=user, shipment_id=str(s2.id), status="inspecting")
        shipment_complete(
            user=user,
            shipment_id=str(s2.id),
            details=[
                {
                    "po_line_id": str(order.lines.first().id),
                    "item_id": str(item.id),
                    "quantity": Decimal("200.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
            total_logistic_fees=Decimal("0"),
        )

        # Check remaining_quantity của s2 qua serializer
        s2.refresh_from_db()
        from apps.purchasing.api.v1.serializers import ShipmentSerializer

        data = ShipmentSerializer(s2).data
        line_data = next(
            line_item for line_item in data["purchase_order_lines"] if line_item["item_id"] == str(item.id)
        )
        assert Decimal(line_data["quantity"]) == Decimal("600.00")
        assert Decimal(line_data["remaining_quantity"]) == Decimal("0.00")
        assert Decimal(line_data["received_quantity"]) == Decimal("600.00")
