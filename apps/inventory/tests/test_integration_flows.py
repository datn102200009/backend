"""
Integration Tests - End-to-End Scenarios.

Kiểm tra toàn bộ luồng nghiệp vụ thực tế.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from django.db.models import Sum
from rest_framework.test import APIClient

from apps.accounts.models import RolePermission
from apps.inventory.models import StockEntry, StockLedger
from apps.inventory.tests.factories import (
    BOMFactory,
    BOMItemFactory,
    ItemFactory,
    PermissionFactory,
    RoleFactory,
    StockLedgerFactory,
    UserFactory,
    WarehouseFactory,
    WorkOrderFactory,
)


@pytest.mark.django_db
class TestCompleteStockInFlow:
    """Test toàn bộ luồng nhập kho từ đầu đến cuối."""

    @pytest.fixture
    def flow_setup_data(self, warehouse_keeper_user):
        """Setup warehouse, items."""
        warehouse = WarehouseFactory(name="Kho Chính")
        item1 = ItemFactory(item_code="ITEM-001")
        item2 = ItemFactory(item_code="ITEM-002")

        return {
            "user": warehouse_keeper_user,
            "warehouse": warehouse,
            "items": [item1, item2],
        }

    def test_full_stock_in_flow(self, flow_setup_data):
        """
        Luồng đầy đủ nhập kho:
        1. Tạo phiếu nhập (draft)
        2. Phê duyệt phiếu
        3. Kiểm tra tồn kho được cập nhật
        """
        from apps.inventory.services import stock_in_approve, stock_in_create

        user = flow_setup_data["user"]
        warehouse = flow_setup_data["warehouse"]
        items = flow_setup_data["items"]

        # STEP 1: Tạo phiếu nhập
        stock_entry = stock_in_create(
            user=user,
            name="SI-2024-001",
            posting_date=datetime.now(),
            details=[
                {
                    "item_id": str(items[0].id),
                    "quantity": Decimal("100.00"),
                    "target_warehouse_id": str(warehouse.id),
                },
                {
                    "item_id": str(items[1].id),
                    "quantity": Decimal("50.00"),
                    "target_warehouse_id": str(warehouse.id),
                },
            ],
            remarks="Nhập hàng từ nhà cung cấp",
        )

        # Verify phiếu ở trạng thái draft
        assert stock_entry.status == "draft"
        assert stock_entry.details.count() == 2

        # STEP 2: Phê duyệt phiếu
        approved_entry = stock_in_approve(user=user, stock_entry_id=str(stock_entry.id))

        # Verify phiếu ở trạng thái posted
        assert approved_entry.status == "posted"

        # STEP 3: Kiểm tra tồn kho
        ledger1 = StockLedger.objects.filter(
            item=items[0],
            warehouse=warehouse,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]

        ledger2 = StockLedger.objects.filter(
            item=items[1],
            warehouse=warehouse,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]

        assert ledger1 == Decimal("100.00")
        assert ledger2 == Decimal("50.00")


@pytest.mark.django_db
class TestCompleteStockIssueFlow:
    """Test toàn bộ luồng xuất kho sản xuất."""

    def test_full_stock_issue_flow(self, warehouse_keeper_user):
        """
        Luồng đầy đủ xuất kho sản xuất:
        1. Chuẩn bị tồn kho
        2. Tạo phiếu xuất (auto-fetch từ BOM)
        3. Phê duyệt
        4. Kiểm tra tồn kho trừ đi
        """
        from apps.inventory.services import stock_issue_approve, stock_issue_create

        # Setup
        user = warehouse_keeper_user

        warehouse = WarehouseFactory()
        material = ItemFactory()

        # Tạo tồn kho ban đầu
        StockLedgerFactory(
            item=material,
            warehouse=warehouse,
            actual_quantity=Decimal("100.00"),
        )

        initial_stock = Decimal("100.00")

        # STEP 1: Tạo phiếu xuất
        stock_entry = stock_issue_create(
            user=user,
            name="SO-2024-001",
            posting_date=datetime.now(),
            source_warehouse_id=str(warehouse.id),
            details=[
                {
                    "item_id": str(material.id),
                    "quantity": Decimal("50.00"),
                }
            ],
        )

        assert stock_entry.status == "draft"
        assert stock_entry.details.first().quantity == Decimal("50.00")

        # STEP 2: Phê duyệt
        approved_entry = stock_issue_approve(user=user, stock_entry_id=str(stock_entry.id))
        assert approved_entry.status == "posted"

        # STEP 3: Kiểm tra tồn kho
        final_stock = StockLedger.objects.filter(
            item=material,
            warehouse=warehouse,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]

        # Tồn kho = 100 - 50 = 50
        assert final_stock == Decimal("50.00")


@pytest.mark.django_db
class TestCompleteStockTransferFlow:
    """Test toàn bộ luồng chuyển kho nội bộ."""

    def test_full_transfer_with_double_transaction(self, warehouse_keeper_user):
        """
        Luồng chuyển kho:
        1. Chuẩn bị tồn kho tại warehouse 1
        2. Tạo phiếu chuyển
        3. Phê duyệt (double transaction)
        4. Kiểm tra cả 2 warehouse
        """
        from apps.inventory.services import stock_transfer_approve, stock_transfer_create

        # Setup
        user = warehouse_keeper_user

        warehouse1 = WarehouseFactory(name="Kho 1")
        warehouse2 = WarehouseFactory(name="Kho 2")
        item = ItemFactory()

        # Tạo tồn kho tại warehouse 1
        StockLedgerFactory(
            item=item,
            warehouse=warehouse1,
            actual_quantity=Decimal("100.00"),
        )

        # STEP 1: Tạo phiếu chuyển
        stock_entry = stock_transfer_create(
            user=user,
            name="ST-2024-001",
            posting_date=datetime.now(),
            source_warehouse_id=str(warehouse1.id),
            target_warehouse_id=str(warehouse2.id),
            details=[
                {
                    "item_id": str(item.id),
                    "quantity": Decimal("60.00"),
                }
            ],
        )

        assert stock_entry.status == "draft"

        # STEP 2: Phê duyệt
        approved_entry = stock_transfer_approve(
            user=user,
            stock_entry_id=str(stock_entry.id),
        )
        assert approved_entry.status == "posted"

        # STEP 3: Kiểm tra tồn kho tại cả 2 warehouse
        stock_w1 = StockLedger.objects.filter(
            item=item,
            warehouse=warehouse1,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]

        stock_w2 = StockLedger.objects.filter(
            item=item,
            warehouse=warehouse2,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]

        # Warehouse 1: 100 - 60 = 40
        assert stock_w1 == Decimal("40.00")

        # Warehouse 2: 0 + 60 = 60
        assert stock_w2 == Decimal("60.00")

        # Verify double transaction được tạo
        ledger_entries = StockLedger.objects.filter(voucher_number="ST-2024-001").count()
        # 1 item * 2 transactions (out + in) = 2
        assert ledger_entries == 2


@pytest.mark.django_db
class TestCompleteAPIFlow:
    """Test toàn bộ luồng thông qua API."""

    def test_api_stock_in_workflow(self, authenticated_api_client):
        """Kiểm tra luồng nhập kho thông qua REST API."""
        import json

        # Setup
        warehouse = WarehouseFactory()
        item = ItemFactory()

        # STEP 1: Tạo phiếu qua API
        payload = {
            "name": "SI-API-001",
            "posting_date": datetime.now().isoformat(),
            "remarks": "API test",
            "details": [
                {
                    "item_id": str(item.id),
                    "quantity": "75.00",
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
        }

        response = authenticated_api_client.post(
            "/api/v1/inventory/stock-in/create/",
            data=payload,
            format="json",
        )

        assert response.status_code == 201
        entry_id = response.data["id"]
        assert response.data["status"] == "draft"

        response = authenticated_api_client.post(
            f"/api/v1/inventory/stock-in/{entry_id}/approve/",
        )

        assert response.status_code == 200
        assert response.data["status"] == "posted"

        response = authenticated_api_client.get(
            f"/api/v1/inventory/stock-ledger/balance/?warehouse_id={warehouse.id}",
        )

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["total_quantity"] == 75.0


@pytest.mark.django_db
class TestComplexScenarios:
    """Test các kịch bản phức tạp."""

    def test_multiple_stock_operations_sequence(self, warehouse_keeper_user):
        """
        Test chuỗi nhiều phiếu:
        1. Nhập 100 + 100 = 200
        2. Xuất 50
        3. Chuyển 30 tới kho khác
        4. Kiểm tra tồn kho cuối cùng: 120
        """
        from apps.inventory.services import (
            stock_in_approve,
            stock_in_create,
            stock_transfer_approve,
            stock_transfer_create,
        )

        user = warehouse_keeper_user

        warehouse1 = WarehouseFactory()
        warehouse2 = WarehouseFactory()
        item = ItemFactory()

        # STEP 1: Nhập 2 lần
        for i, qty in enumerate([100, 100]):
            entry = stock_in_create(
                user=user,
                name=f"SI-{i+1}",
                posting_date=datetime.now(),
                details=[
                    {
                        "item_id": str(item.id),
                        "quantity": Decimal(str(qty)),
                        "target_warehouse_id": str(warehouse1.id),
                    }
                ],
            )
            stock_in_approve(user=user, stock_entry_id=str(entry.id))

        # Verify tồn kho = 200
        stock = StockLedger.objects.filter(
            item=item,
            warehouse=warehouse1,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]
        assert stock == Decimal("200.00")

        # STEP 2: Xuất 50
        from apps.inventory.services import stock_issue_approve, stock_issue_create

        issue_entry = stock_issue_create(
            user=user,
            name="SO-1",
            posting_date=datetime.now(),
            source_warehouse_id=str(warehouse1.id),
            details=[
                {
                    "item_id": str(item.id),
                    "quantity": Decimal("50.00"),
                }
            ],
        )
        stock_issue_approve(user=user, stock_entry_id=str(issue_entry.id))

        # Verify tồn kho = 150
        stock = StockLedger.objects.filter(
            item=item,
            warehouse=warehouse1,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]
        assert stock == Decimal("150.00")

        # STEP 3: Chuyển 30
        transfer_entry = stock_transfer_create(
            user=user,
            name="ST-1",
            posting_date=datetime.now(),
            source_warehouse_id=str(warehouse1.id),
            target_warehouse_id=str(warehouse2.id),
            details=[
                {
                    "item_id": str(item.id),
                    "quantity": Decimal("30.00"),
                }
            ],
        )
        stock_transfer_approve(user=user, stock_entry_id=str(transfer_entry.id))

        # STEP 4: Verify cuối cùng
        stock_w1 = StockLedger.objects.filter(
            item=item,
            warehouse=warehouse1,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]

        stock_w2 = StockLedger.objects.filter(
            item=item,
            warehouse=warehouse2,
        ).aggregate(
            total=Sum("actual_quantity")
        )["total"]

        # W1: 150 - 30 = 120
        assert stock_w1 == Decimal("120.00")
        # W2: 0 + 30 = 30
        assert stock_w2 == Decimal("30.00")
