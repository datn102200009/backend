"""
Tests for stock in services.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from apps.accounts.models import Permission, RolePermission
from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.inventory.services import stock_in_approve, stock_in_create
from apps.inventory.tests.factories import (
    ItemFactory,
    PermissionFactory,
    RoleFactory,
    StockEntryDetailFactory,
    StockEntryFactory,
    UserFactory,
    WarehouseFactory,
)


@pytest.mark.django_db
class TestStockInCreate:
    """Test suite cho stock_in_create service."""

    @pytest.fixture
    def setup_data(self):
        """Setup data cần thiết."""
        warehouse = WarehouseFactory(name="Kho Chính")
        item = ItemFactory(item_code="ITEM-001")
        return {"warehouse": warehouse, "item": item}

    def test_stock_in_create_success(self, warehouse_keeper_user, setup_data):
        """Test tạo phiếu nhập kho thành công."""
        user = warehouse_keeper_user
        warehouse = setup_data["warehouse"]
        item = setup_data["item"]

        # Test
        stock_entry = stock_in_create(
            user=user,
            name="SI-2024-001",
            posting_date=datetime.now(),
            details=[
                {
                    "item_id": str(item.id),
                    "quantity": Decimal("100.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
            remarks="Nhập từ nhà cung cấp",
        )

        # Assert
        assert stock_entry.name == "SI-2024-001"
        assert stock_entry.purpose == "receipt"
        assert stock_entry.status == "draft"
        assert stock_entry.remarks == "Nhập từ nhà cung cấp"
        assert stock_entry.details.count() == 1
        assert stock_entry.details.first().quantity == Decimal("100.00")

    def test_stock_in_create_no_permission(self, setup_data):
        """Test tạo phiếu nhập kho mà không có quyền."""
        warehouse = setup_data["warehouse"]
        item = setup_data["item"]
        user = UserFactory(role=RoleFactory())  # Không có quyền

        # Test
        with pytest.raises(PermissionException):
            stock_in_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                details=[
                    {
                        "item_id": str(item.id),
                        "quantity": Decimal("100.00"),
                        "target_warehouse_id": str(warehouse.id),
                    }
                ],
            )

    def test_stock_in_create_no_details(self, warehouse_keeper_user):
        """Test tạo phiếu nhập kho nhưng không có chi tiết."""
        user = warehouse_keeper_user

        # Test
        with pytest.raises(ValidationException) as exc_info:
            stock_in_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                details=[],
            )

        assert "ít nhất một chi tiết" in str(exc_info.value)

    def test_stock_in_create_duplicate_name(self, warehouse_keeper_user, setup_data):
        """Test tạo phiếu nhập kho với tên trùng lặp."""
        user = warehouse_keeper_user
        warehouse = setup_data["warehouse"]
        item = setup_data["item"]

        # Tạo phiếu đầu tiên
        stock_in_create(
            user=user,
            name="SI-2024-001",
            posting_date=datetime.now(),
            details=[
                {
                    "item_id": str(item.id),
                    "quantity": Decimal("100.00"),
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
        )

        # Tạo phiếu thứ hai với tên trùng
        with pytest.raises(ValidationException) as exc_info:
            stock_in_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                details=[
                    {
                        "item_id": str(item.id),
                        "quantity": Decimal("100.00"),
                        "target_warehouse_id": str(warehouse.id),
                    }
                ],
            )

        assert "đã tồn tại" in str(exc_info.value)

    def test_stock_in_create_invalid_item(self, warehouse_keeper_user, setup_data):
        """Test tạo phiếu nhập kho với item không tồn tại."""
        user = warehouse_keeper_user
        warehouse = setup_data["warehouse"]

        # Test
        with pytest.raises(NotFoundException) as exc_info:
            stock_in_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                details=[
                    {
                        "item_id": "00000000-0000-0000-0000-000000000000",
                        "quantity": Decimal("100.00"),
                        "target_warehouse_id": str(warehouse.id),
                    }
                ],
            )

        assert "Item" in str(exc_info.value) and "không tồn tại" in str(exc_info.value)

    def test_stock_in_create_invalid_warehouse(self, warehouse_keeper_user, setup_data):
        """Test tạo phiếu nhập kho với warehouse không tồn tại."""
        user = warehouse_keeper_user
        item = setup_data["item"]

        # Test
        with pytest.raises(NotFoundException) as exc_info:
            stock_in_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                details=[
                    {
                        "item_id": str(item.id),
                        "quantity": Decimal("100.00"),
                        "target_warehouse_id": "00000000-0000-0000-0000-000000000000",
                    }
                ],
            )

        assert "Warehouse" in str(exc_info.value) and "không tồn tại" in str(exc_info.value)


@pytest.mark.django_db
class TestStockInApprove:
    """Test suite cho stock_in_approve service."""

    @pytest.fixture
    def setup_stock_entry(self):
        """Setup phiếu stock entry."""
        entry = StockEntryFactory(purpose="receipt", status="draft")
        StockEntryDetailFactory(parent=entry)
        return entry

    def test_stock_in_approve_success(self, warehouse_keeper_user, setup_stock_entry):
        """Test phê duyệt phiếu nhập kho thành công."""
        user = warehouse_keeper_user
        stock_entry = setup_stock_entry

        # Test
        approved_entry = stock_in_approve(
            user=user,
            stock_entry_id=str(stock_entry.id),
        )

        # Assert
        assert approved_entry.status == "posted"
        # Kiểm tra StockLedger được tạo
        assert approved_entry.details.count() > 0

    def test_stock_in_approve_no_permission(self, setup_stock_entry):
        """Test phê duyệt phiếu nhập kho mà không có quyền."""
        stock_entry = setup_stock_entry
        user = UserFactory(role=RoleFactory())  # Không có quyền

        # Test
        with pytest.raises(PermissionException):
            stock_in_approve(
                user=user,
                stock_entry_id=str(stock_entry.id),
            )

    def test_stock_in_approve_not_found(self, warehouse_keeper_user):
        """Test phê duyệt phiếu nhập kho không tồn tại."""
        user = warehouse_keeper_user

        # Test
        with pytest.raises(NotFoundException) as exc_info:
            stock_in_approve(
                user=user,
                stock_entry_id="00000000-0000-0000-0000-000000000000",
            )

        assert "không tồn tại" in str(exc_info.value)

    def test_stock_in_approve_invalid_status(self, warehouse_keeper_user):
        """Test phê duyệt phiếu nhập kho ở trạng thái không hợp lệ."""
        user = warehouse_keeper_user
        # Tạo phiếu ở trạng thái posted
        entry = StockEntryFactory(purpose="receipt", status="posted")

        # Test
        with pytest.raises(ValidationException) as exc_info:
            stock_in_approve(
                user=user,
                stock_entry_id=str(entry.id),
            )

        assert "Draft" in str(exc_info.value)
