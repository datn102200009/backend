"""
Tests for inventory selectors.
"""

from decimal import Decimal

import pytest

from apps.inventory.selectors import (
    bom_by_item,
    bom_list_active,
    item_check_duplicate_code,
    item_list_active,
    item_search,
    stock_entry_list_by_status,
    stock_ledger_balance_by_item_warehouse,
    stock_ledger_balance_by_warehouse,
)
from apps.inventory.tests.factories import (
    BOMFactory,
    ItemFactory,
    ItemGroupFactory,
    StockEntryFactory,
    StockLedgerFactory,
    WarehouseFactory,
)


@pytest.mark.django_db
class TestStockEntrySelectors:
    """Test suite cho stock entry selectors."""

    def test_stock_entry_list_by_status_draft(self):
        """Test lấy phiếu stock entry ở trạng thái draft."""
        # Setup
        StockEntryFactory(status="draft", purpose="receipt")
        StockEntryFactory(status="draft", purpose="receipt")
        StockEntryFactory(status="posted", purpose="receipt")

        # Test
        result = stock_entry_list_by_status("draft")

        # Assert
        assert result.count() == 2
        assert all(entry.status == "draft" for entry in result)

    def test_stock_entry_list_by_status_with_purpose(self):
        """Test lấy phiếu stock entry theo trạng thái và mục đích."""
        # Setup
        StockEntryFactory(status="draft", purpose="receipt")
        StockEntryFactory(status="draft", purpose="issue")
        StockEntryFactory(status="draft", purpose="transfer")

        # Test
        result = stock_entry_list_by_status("draft", purpose="receipt")

        # Assert
        assert result.count() == 1
        assert result.first().purpose == "receipt"

    def test_stock_entry_list_ordering(self):
        """Test danh sách phiếu được sắp xếp theo ngày tạo giảm dần."""
        # Setup
        entry1 = StockEntryFactory(status="draft")
        entry2 = StockEntryFactory(status="draft")
        entry3 = StockEntryFactory(status="draft")

        # Test
        result = stock_entry_list_by_status("draft")

        # Assert - entry3 được tạo cuối cùng nên ở đầu
        assert list(result)[0].id == entry3.id


@pytest.mark.django_db
class TestStockLedgerSelectors:
    """Test suite cho stock ledger selectors."""

    def test_stock_ledger_balance_by_item_warehouse(self):
        """Test tính tồn kho item trong warehouse."""
        # Setup
        item = ItemFactory()
        warehouse = WarehouseFactory()
        StockLedgerFactory(item=item, warehouse=warehouse, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=item, warehouse=warehouse, actual_quantity=Decimal("50.00"))
        StockLedgerFactory(item=item, warehouse=warehouse, actual_quantity=Decimal("-20.00"))

        # Test
        balance = stock_ledger_balance_by_item_warehouse(item, warehouse)

        # Assert
        assert balance == Decimal("130.00")

    def test_stock_ledger_balance_by_item_warehouse_zero(self):
        """Test tồn kho item không tồn tại trong warehouse."""
        # Setup
        item = ItemFactory()
        warehouse = WarehouseFactory()

        # Test
        balance = stock_ledger_balance_by_item_warehouse(item, warehouse)

        # Assert
        assert balance == Decimal("0.00")

    def test_stock_ledger_balance_by_warehouse(self):
        """Test tồn kho tất cả items trong warehouse."""
        # Setup
        warehouse = WarehouseFactory()
        item1 = ItemFactory()
        item2 = ItemFactory()

        StockLedgerFactory(item=item1, warehouse=warehouse, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=item2, warehouse=warehouse, actual_quantity=Decimal("50.00"))

        # Test
        result = stock_ledger_balance_by_warehouse(warehouse)

        # Assert
        assert result.count() == 2


@pytest.mark.django_db
class TestItemSelectors:
    """Test suite cho item selectors."""

    def test_item_list_active(self):
        """Test lấy danh sách sản phẩm hoạt động."""
        # Setup
        ItemFactory(status="active")
        ItemFactory(status="active")
        ItemFactory(status="inactive")
        ItemFactory(status="active", is_active=False)

        # Test
        result = item_list_active()

        # Assert
        assert result.count() == 2
        assert all(item.status == "active" and item.is_active for item in result)

    def test_item_list_by_group(self):
        """Test lấy danh sách sản phẩm theo nhóm."""
        # Setup
        group1 = ItemGroupFactory()
        group2 = ItemGroupFactory()

        ItemFactory(item_group=group1, status="active")
        ItemFactory(item_group=group1, status="active")
        ItemFactory(item_group=group2, status="active")

        # Test
        result = item_list_active().filter(item_group=group1)

        # Assert
        assert result.count() == 2

    def test_item_search_by_code(self):
        """Test tìm kiếm sản phẩm theo mã."""
        # Setup
        ItemFactory(item_code="ITEM-001", status="active")
        ItemFactory(item_code="ITEM-002", status="active")
        ItemFactory(item_code="OTHER-001", status="active")

        # Test
        result = item_search("ITEM")

        # Assert
        assert result.count() == 2

    def test_item_search_by_name(self):
        """Test tìm kiếm sản phẩm theo tên."""
        # Setup
        ItemFactory(item_name="Product A", status="active")
        ItemFactory(item_name="Product B", status="active")
        ItemFactory(item_name="Other Item", status="active")

        # Test
        result = item_search("Product")

        # Assert
        assert result.count() == 2

    def test_item_search_case_insensitive(self):
        """Test tìm kiếm sản phẩm không phân biệt hoa thường."""
        # Setup
        ItemFactory(item_code="ITEM-001", status="active")

        # Test
        result = item_search("item")

        # Assert
        assert result.count() == 1

    def test_item_check_duplicate_code_exists(self):
        """Test kiểm tra mã sản phẩm đã tồn tại."""
        # Setup
        ItemFactory(item_code="ITEM-001")

        # Test
        result = item_check_duplicate_code("ITEM-001")

        # Assert
        assert result is True

    def test_item_check_duplicate_code_not_exists(self):
        """Test kiểm tra mã sản phẩm không tồn tại."""
        # Test
        result = item_check_duplicate_code("ITEM-999")

        # Assert
        assert result is False

    def test_item_check_duplicate_code_exclude_id(self):
        """Test kiểm tra mã sản phẩm (loại trừ item được update)."""
        # Setup
        item = ItemFactory(item_code="ITEM-001")

        # Test - loại trừ item đó
        result = item_check_duplicate_code("ITEM-001", exclude_id=str(item.id))

        # Assert
        assert result is False


@pytest.mark.django_db
class TestBOMSelectors:
    """Test suite cho BOM selectors."""

    def test_bom_list_active(self):
        """Test lấy danh sách BOM hoạt động."""
        # Setup
        BOMFactory(status="active")
        BOMFactory(status="active")
        BOMFactory(status="inactive")
        BOMFactory(status="active", is_active=False)

        # Test
        result = bom_list_active()

        # Assert
        assert result.count() == 2
        assert all(bom.status == "active" and bom.is_active for bom in result)

    def test_bom_by_item(self):
        """Test lấy BOM của một sản phẩm."""
        # Setup
        item = ItemFactory()
        BOMFactory(item=item, status="active")
        BOMFactory(item=item, status="active")
        BOMFactory(item=ItemFactory(), status="active")

        # Test
        result = bom_by_item(str(item.id))

        # Assert
        assert result.count() == 2

    def test_bom_by_item_inactive(self):
        """Test BOM không hoạt động không được trả về."""
        # Setup
        item = ItemFactory()
        BOMFactory(item=item, status="active")
        BOMFactory(item=item, status="inactive")

        # Test
        result = bom_by_item(str(item.id))

        # Assert
        assert result.count() == 1
