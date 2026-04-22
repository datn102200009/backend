"""
Tests for stock issue services.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from apps.accounts.models import Permission, RolePermission
from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.inventory.services import stock_issue_approve, stock_issue_for_manufacturing_create
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
    WorkOrderFactory,
)


@pytest.mark.django_db
class TestStockIssueForManufacturingCreate:
    """Test suite cho stock_issue_for_manufacturing_create service."""

    @pytest.fixture
    def setup_user_with_permission(self):
        """Setup user với quyền stock_issue."""
        role = RoleFactory(name="Thủ kho")
        perm = PermissionFactory(code="inventory.stock_issue")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role)
        return user

    @pytest.fixture
    def setup_manufacturing_data(self):
        """Setup data cho xuất kho sản xuất."""
        warehouse = WarehouseFactory(name="Kho Chính")

        # Tạo sản phẩm chính (sản phẩm được sản xuất)
        main_item = ItemFactory(item_code="PRODUCT-001")

        # Tạo các linh kiện (materials)
        material1 = ItemFactory(item_code="MATERIAL-001")
        material2 = ItemFactory(item_code="MATERIAL-002")

        # Tạo BOM cho sản phẩm
        bom = BOMFactory(item=main_item)
        BOMItemFactory(bom=bom, item=material1, qty=Decimal("5.00"))
        BOMItemFactory(bom=bom, item=material2, qty=Decimal("3.00"))

        # Tạo lệnh sản xuất
        work_order = WorkOrderFactory(item=main_item, qty=Decimal("10.00"))

        # Tạo tồn kho cho các linh kiện
        StockLedgerFactory(item=material1, warehouse=warehouse, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=material2, warehouse=warehouse, actual_quantity=Decimal("100.00"))

        return {
            "warehouse": warehouse,
            "work_order": work_order,
            "bom": bom,
            "material1": material1,
            "material2": material2,
        }

    def test_stock_issue_create_success(self, setup_user_with_permission, setup_manufacturing_data):
        """Test tạo phiếu xuất kho cho sản xuất thành công."""
        user = setup_user_with_permission
        data = setup_manufacturing_data

        # Test
        stock_entry = stock_issue_for_manufacturing_create(
            user=user,
            name="SI-2024-001",
            posting_date=datetime.now(),
            work_order_id=str(data["work_order"].id),
            source_warehouse_id=str(data["warehouse"].id),
            remarks="Xuất cho lệnh sản xuất",
        )

        # Assert
        assert stock_entry.name == "SI-2024-001"
        assert stock_entry.purpose == "issue"
        assert stock_entry.status == "draft"
        assert stock_entry.details.count() == 2  # 2 linh kiện

        # Kiểm tra số lượng
        details = list(stock_entry.details.all())
        assert details[0].quantity == Decimal("50.00")  # 5 * 10
        assert details[1].quantity == Decimal("30.00")  # 3 * 10

    def test_stock_issue_create_no_permission(self, setup_manufacturing_data):
        """Test tạo phiếu xuất kho mà không có quyền."""
        data = setup_manufacturing_data
        user = UserFactory(role=RoleFactory())

        with pytest.raises(PermissionException):
            stock_issue_for_manufacturing_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                work_order_id=str(data["work_order"].id),
                source_warehouse_id=str(data["warehouse"].id),
            )

    def test_stock_issue_create_invalid_work_order(self, setup_user_with_permission):
        """Test tạo phiếu xuất kho với work order không tồn tại."""
        user = setup_user_with_permission
        warehouse = WarehouseFactory()

        with pytest.raises(NotFoundException) as exc_info:
            stock_issue_for_manufacturing_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                work_order_id="00000000-0000-0000-0000-000000000000",
                source_warehouse_id=str(warehouse.id),
            )

        assert "Work Order" in str(exc_info.value)

    def test_stock_issue_create_no_bom(self, setup_user_with_permission):
        """Test tạo phiếu xuất kho khi sản phẩm không có BOM."""
        user = setup_user_with_permission
        warehouse = WarehouseFactory()

        # Tạo sản phẩm và work order nhưng không có BOM
        item = ItemFactory()
        work_order = WorkOrderFactory(item=item)

        with pytest.raises(NotFoundException) as exc_info:
            stock_issue_for_manufacturing_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                work_order_id=str(work_order.id),
                source_warehouse_id=str(warehouse.id),
            )

        assert "BOM" in str(exc_info.value)

    def test_stock_issue_create_insufficient_stock(self, setup_user_with_permission):
        """Test tạo phiếu xuất kho khi không đủ tồn kho."""
        user = setup_user_with_permission
        warehouse = WarehouseFactory()

        # Tạo sản phẩm, BOM, work order
        main_item = ItemFactory()
        material = ItemFactory()
        bom = BOMFactory(item=main_item)
        BOMItemFactory(bom=bom, item=material, qty=Decimal("100.00"))
        work_order = WorkOrderFactory(item=main_item, qty=Decimal("10.00"))

        # Chỉ có 500 nhưng cần 1000 (100 * 10)
        StockLedgerFactory(item=material, warehouse=warehouse, actual_quantity=Decimal("500.00"))

        with pytest.raises(ValidationException) as exc_info:
            stock_issue_for_manufacturing_create(
                user=user,
                name="SI-2024-001",
                posting_date=datetime.now(),
                work_order_id=str(work_order.id),
                source_warehouse_id=str(warehouse.id),
            )

        assert "Không đủ tồn kho" in str(exc_info.value)


@pytest.mark.django_db
class TestStockIssueApprove:
    """Test suite cho stock_issue_approve service."""

    @pytest.fixture
    def setup_user_with_permission(self):
        """Setup user với quyền stock_issue_approve."""
        role = RoleFactory(name="Thủ kho")
        perm = PermissionFactory(code="inventory.stock_issue_approve")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role)
        return user

    def test_stock_issue_approve_success(self, setup_user_with_permission):
        """Test phê duyệt phiếu xuất kho thành công."""
        user = setup_user_with_permission
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

    def test_stock_issue_approve_invalid_status(self, setup_user_with_permission):
        """Test phê duyệt phiếu xuất kho ở trạng thái không hợp lệ."""
        user = setup_user_with_permission
        entry = StockEntryFactory(purpose="issue", status="posted")

        with pytest.raises(ValidationException) as exc_info:
            stock_issue_approve(
                user=user,
                stock_entry_id=str(entry.id),
            )

        assert "Draft" in str(exc_info.value)
