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
    def setup_user_with_permission(self):
        """Setup user với quyền stock_in."""
        role = RoleFactory(name="Thủ kho")
        perm = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role)
        return user

    @pytest.fixture
    def setup_data(self):
        """Setup data cần thiết."""
        warehouse = WarehouseFactory(name="Kho Chính")
        item = ItemFactory(item_code="ITEM-001")
        return {"warehouse": warehouse, "item": item}

    def test_stock_in_create_success(self, setup_user_with_permission, setup_data):
        """Test tạo phiếu nhập kho thành công."""
        user = setup_user_with_permission
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

    def test_stock_in_create_no_details(self, setup_user_with_permission):
        """Test tạo phiếu nhập kho nhưng không có chi tiết."""
        user = setup_user_with_permission

        # Test
        with pytest.raises(ValidationException) as exc_info:
            stock_in_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                details=[],
            )

        assert "ít nhất một chi tiết" in str(exc_info.value)

    def test_stock_in_create_duplicate_name(self, setup_user_with_permission, setup_data):
        """Test tạo phiếu nhập kho với tên trùng lặp."""
        user = setup_user_with_permission
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

    def test_stock_in_create_invalid_item(self, setup_user_with_permission, setup_data):
        """Test tạo phiếu nhập kho với item không tồn tại."""
        user = setup_user_with_permission
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

    def test_stock_in_create_invalid_warehouse(self, setup_user_with_permission, setup_data):
        """Test tạo phiếu nhập kho với warehouse không tồn tại."""
        user = setup_user_with_permission
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
    def setup_user_with_permission(self):
        """Setup user với quyền stock_in_approve."""
        role = RoleFactory(name="Thủ kho")
        perm = PermissionFactory(code="inventory.stock_in_approve")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role)
        return user

    @pytest.fixture
    def setup_stock_entry(self):
        """Setup phiếu stock entry."""
        entry = StockEntryFactory(purpose="receipt", status="draft")
        StockEntryDetailFactory(parent=entry)
        return entry

    def test_stock_in_approve_success(self, setup_user_with_permission, setup_stock_entry):
        """Test phê duyệt phiếu nhập kho thành công."""
        user = setup_user_with_permission
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

    def test_stock_in_approve_not_found(self, setup_user_with_permission):
        """Test phê duyệt phiếu nhập kho không tồn tại."""
        user = setup_user_with_permission

        # Test
        with pytest.raises(NotFoundException) as exc_info:
            stock_in_approve(
                user=user,
                stock_entry_id="00000000-0000-0000-0000-000000000000",
            )

        assert "không tồn tại" in str(exc_info.value)

    def test_stock_in_approve_invalid_status(self, setup_user_with_permission):
        """Test phê duyệt phiếu nhập kho ở trạng thái không hợp lệ."""
        user = setup_user_with_permission
        # Tạo phiếu ở trạng thái posted
        entry = StockEntryFactory(purpose="receipt", status="posted")

        # Test
        with pytest.raises(ValidationException) as exc_info:
            stock_in_approve(
                user=user,
                stock_entry_id=str(entry.id),
            )

        assert "Draft" in str(exc_info.value)
