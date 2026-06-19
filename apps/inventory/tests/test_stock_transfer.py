"""
Tests for stock transfer services.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from apps.accounts.models import RolePermission
from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.inventory.services import stock_transfer_approve, stock_transfer_create
from apps.inventory.tests.factories import (
    ItemFactory,
    PermissionFactory,
    RoleFactory,
    StockEntryFactory,
    StockLedgerFactory,
    UserFactory,
    WarehouseFactory,
)


@pytest.mark.django_db
class TestStockTransferCreate:
    """Test suite cho stock_transfer_create service."""

    @pytest.fixture
    def setup_warehouses_and_stock(self):
        """Setup kho và tồn kho."""
        warehouse1 = WarehouseFactory(name="Kho 1")
        warehouse2 = WarehouseFactory(name="Kho 2")
        item = ItemFactory()

        # Tạo tồn kho ở warehouse1
        StockLedgerFactory(item=item, warehouse=warehouse1, actual_quantity=Decimal("100.00"))

        return {
            "warehouse1": warehouse1,
            "warehouse2": warehouse2,
            "item": item,
        }

    def test_stock_transfer_create_success(self, warehouse_keeper_user, setup_warehouses_and_stock):
        """Test tạo phiếu chuyển kho thành công."""
        user = warehouse_keeper_user
        data = setup_warehouses_and_stock

        # Test
        stock_entry = stock_transfer_create(
            user=user,
            name="ST-2024-001",
            source_warehouse_id=str(data["warehouse1"].id),
            target_warehouse_id=str(data["warehouse2"].id),
            details=[
                {
                    "item_id": str(data["item"].id),
                    "quantity": Decimal("50.00"),
                }
            ],
            remarks="Chuyển kho",
        )

        # Assert
        assert stock_entry.name == "ST-2024-001"
        assert stock_entry.purpose == "transfer"
        assert stock_entry.status == "draft"
        assert stock_entry.details.count() == 1

    def test_stock_transfer_create_no_permission(self, setup_warehouses_and_stock):
        """Test tạo phiếu chuyển kho mà không có quyền."""
        data = setup_warehouses_and_stock
        user = UserFactory(role=RoleFactory())

        with pytest.raises(PermissionException):
            stock_transfer_create(
                user=user,
                name="ST-2024-001",
                source_warehouse_id=str(data["warehouse1"].id),
                target_warehouse_id=str(data["warehouse2"].id),
                details=[
                    {
                        "item_id": str(data["item"].id),
                        "quantity": Decimal("50.00"),
                    }
                ],
            )

    def test_stock_transfer_create_same_warehouse(self, warehouse_keeper_user, setup_warehouses_and_stock):
        """Test tạo phiếu chuyển kho với kho nguồn = kho đích."""
        user = warehouse_keeper_user
        data = setup_warehouses_and_stock

        with pytest.raises(ValidationException) as exc_info:
            stock_transfer_create(
                user=user,
                name="ST-2024-001",
                source_warehouse_id=str(data["warehouse1"].id),
                target_warehouse_id=str(data["warehouse1"].id),
                details=[
                    {
                        "item_id": str(data["item"].id),
                        "quantity": Decimal("50.00"),
                    }
                ],
            )

        assert "khác nhau" in str(exc_info.value)

    def test_stock_transfer_create_insufficient_stock(self, warehouse_keeper_user):
        """Test tạo phiếu chuyển kho khi không đủ tồn kho."""
        user = warehouse_keeper_user
        warehouse1 = WarehouseFactory()
        warehouse2 = WarehouseFactory()
        item = ItemFactory()

        # Chỉ có 50 nhưng muốn chuyển 100
        StockLedgerFactory(item=item, warehouse=warehouse1, actual_quantity=Decimal("50.00"))

        with pytest.raises(ValidationException) as exc_info:
            stock_transfer_create(
                user=user,
                name="ST-2024-001",
                source_warehouse_id=str(warehouse1.id),
                target_warehouse_id=str(warehouse2.id),
                details=[
                    {
                        "item_id": str(item.id),
                        "quantity": Decimal("100.00"),
                    }
                ],
            )

        assert "Không đủ tồn kho" in str(exc_info.value)

    def test_stock_transfer_create_invalid_item(self, warehouse_keeper_user, setup_warehouses_and_stock):
        """Test tạo phiếu chuyển kho với item không tồn tại."""
        user = warehouse_keeper_user
        data = setup_warehouses_and_stock

        with pytest.raises(NotFoundException) as exc_info:
            stock_transfer_create(
                user=user,
                name="ST-2024-001",
                source_warehouse_id=str(data["warehouse1"].id),
                target_warehouse_id=str(data["warehouse2"].id),
                details=[
                    {
                        "item_id": "00000000-0000-0000-0000-000000000000",
                        "quantity": Decimal("50.00"),
                    }
                ],
            )

        assert "Item" in str(exc_info.value)

    def test_stock_transfer_create_invalid_warehouse(self, warehouse_keeper_user, setup_warehouses_and_stock):
        """Test tạo phiếu chuyển kho với warehouse không tồn tại."""
        user = warehouse_keeper_user
        data = setup_warehouses_and_stock

        with pytest.raises(NotFoundException) as exc_info:
            stock_transfer_create(
                user=user,
                name="ST-2024-001",
                source_warehouse_id="00000000-0000-0000-0000-000000000000",
                target_warehouse_id=str(data["warehouse2"].id),
                details=[
                    {
                        "item_id": str(data["item"].id),
                        "quantity": Decimal("50.00"),
                    }
                ],
            )

        assert "Kho nguồn" in str(exc_info.value)


@pytest.mark.django_db
class TestStockTransferApprove:
    """Test suite cho stock_transfer_approve service."""

    def test_stock_transfer_approve_success(self, warehouse_keeper_user):
        """Test phê duyệt phiếu chuyển kho thành công (Double Transaction)."""
        user = warehouse_keeper_user
        entry = StockEntryFactory(purpose="transfer", status="draft")

        # Test
        approved_entry = stock_transfer_approve(
            user=user,
            stock_entry_id=str(entry.id),
        )

        # Assert
        assert approved_entry.status == "posted"

        # Kiểm tra Double Transaction
        # Mỗi detail sẽ tạo 2 entries (âm ở warehouse1, dương ở warehouse2)
        from apps.inventory.models import StockLedger

        ledger_count = StockLedger.objects.filter(voucher_number=entry.name).count()
        assert ledger_count == entry.details.count() * 2

    def test_stock_transfer_approve_no_permission(self):
        """Test phê duyệt phiếu chuyển kho mà không có quyền."""
        user = UserFactory(role=RoleFactory())
        entry = StockEntryFactory(purpose="transfer", status="draft")

        with pytest.raises(PermissionException):
            stock_transfer_approve(
                user=user,
                stock_entry_id=str(entry.id),
            )

    def test_stock_transfer_approve_invalid_status(self, warehouse_keeper_user):
        """Test phê duyệt phiếu chuyển kho ở trạng thái không hợp lệ."""
        user = warehouse_keeper_user
        entry = StockEntryFactory(purpose="transfer", status="posted")

        with pytest.raises(ValidationException) as exc_info:
            stock_transfer_approve(
                user=user,
                stock_entry_id=str(entry.id),
            )

        assert "Draft" in str(exc_info.value)

    def test_stock_transfer_approve_not_found(self, warehouse_keeper_user):
        """Test phê duyệt phiếu chuyển kho không tồn tại."""
        user = warehouse_keeper_user

        with pytest.raises(NotFoundException) as exc_info:
            stock_transfer_approve(
                user=user,
                stock_entry_id="00000000-0000-0000-0000-000000000000",
            )

        assert "không tồn tại" in str(exc_info.value)
