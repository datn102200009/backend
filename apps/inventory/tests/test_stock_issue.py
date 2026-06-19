"""
Tests for stock issue services.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from apps.accounts.models import Permission, RolePermission
from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.inventory.services import stock_issue_approve, stock_issue_create
from apps.inventory.tests.factories import (
    BOMFactory,
    BOMItemFactory,
    ItemFactory,
    PermissionFactory,
    RoleFactory,
    StockEntryFactory,
    StockLedgerFactory,
    UserFactory,
    WarehouseFactory,
)


@pytest.mark.django_db
class TestStockIssueCreate:
    """Test suite cho stock_issue_create service."""

    @pytest.fixture
    def setup_issue_data(self):
        """Setup data cho xuất kho."""
        warehouse = WarehouseFactory(name="Kho Chính")

        # Tạo các linh kiện (materials)
        material1 = ItemFactory(item_code="MATERIAL-001")
        material2 = ItemFactory(item_code="MATERIAL-002")

        # Tạo tồn kho cho các linh kiện
        StockLedgerFactory(item=material1, warehouse=warehouse, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=material2, warehouse=warehouse, actual_quantity=Decimal("100.00"))

        return {
            "warehouse": warehouse,
            "material1": material1,
            "material2": material2,
        }

    def test_stock_issue_create_success(self, warehouse_keeper_user, setup_issue_data):
        """Test tạo phiếu xuất kho thành công."""
        user = warehouse_keeper_user
        data = setup_issue_data

        # Test
        stock_entry = stock_issue_create(
            user=user,
            name="SI-2024-001",
            source_warehouse_id=str(data["warehouse"].id),
            details=[
                {
                    "item_id": str(data["material1"].id),
                    "quantity": Decimal("50.00"),
                },
                {
                    "item_id": str(data["material2"].id),
                    "quantity": Decimal("30.00"),
                },
            ],
            remarks="Xuất kho test",
        )

        # Assert
        assert stock_entry.name == "SI-2024-001"
        assert stock_entry.purpose == "issue"
        assert stock_entry.status == "draft"
        assert stock_entry.details.count() == 2

        # Kiểm tra số lượng
        details = list(stock_entry.details.all())
        assert details[0].quantity == Decimal("50.00")
        assert details[1].quantity == Decimal("30.00")

    def test_stock_issue_create_no_permission(self, setup_issue_data):
        """Test tạo phiếu xuất kho mà không có quyền."""
        data = setup_issue_data
        user = UserFactory(role=RoleFactory())

        with pytest.raises(PermissionException):
            stock_issue_create(
                user=user,
                name="SI-2024-001",
                source_warehouse_id=str(data["warehouse"].id),
                details=[
                    {
                        "item_id": str(data["material1"].id),
                        "quantity": Decimal("50.00"),
                    }
                ],
            )

    def test_stock_issue_create_insufficient_stock(self, warehouse_keeper_user, setup_issue_data):
        """Test tạo phiếu xuất kho khi không đủ tồn kho."""
        user = warehouse_keeper_user
        data = setup_issue_data

        with pytest.raises(ValidationException) as exc_info:
            stock_issue_create(
                user=user,
                name="SI-2024-001",
                source_warehouse_id=str(data["warehouse"].id),
                details=[
                    {
                        "item_id": str(data["material1"].id),
                        "quantity": Decimal("150.00"),  # Chỉ có 100
                    }
                ],
            )

        assert "Không đủ tồn kho" in str(exc_info.value)


@pytest.mark.django_db
class TestStockIssueApprove:
    """Test suite cho stock_issue_approve service."""

    def test_stock_issue_approve_success(self, warehouse_keeper_user):
        """Test phê duyệt phiếu xuất kho thành công."""
        user = warehouse_keeper_user
        entry = StockEntryFactory(purpose="issue", status="draft")

        # Test
        approved_entry = stock_issue_approve(
            user=user,
            stock_entry_id=str(entry.id),
        )

        # Assert
        assert approved_entry.status == "posted"

    def test_stock_issue_approve_no_permission(self):
        """Test phê duyệt phiếu xuất kho mà không có quyền."""
        user = UserFactory(role=RoleFactory())
        entry = StockEntryFactory(purpose="issue", status="draft")

        with pytest.raises(PermissionException):
            stock_issue_approve(
                user=user,
                stock_entry_id=str(entry.id),
            )

    def test_stock_issue_approve_invalid_status(self, warehouse_keeper_user):
        """Test phê duyệt phiếu xuất kho ở trạng thái không hợp lệ."""
        user = warehouse_keeper_user
        entry = StockEntryFactory(purpose="issue", status="posted")

        with pytest.raises(ValidationException) as exc_info:
            stock_issue_approve(
                user=user,
                stock_entry_id=str(entry.id),
            )

        assert "Draft" in str(exc_info.value)
