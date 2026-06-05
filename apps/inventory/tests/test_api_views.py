"""
Tests for inventory API views.
"""

import json
from datetime import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import RolePermission
from apps.inventory.tests.factories import (
    BOMFactory,
    BOMItemFactory,
    ItemFactory,
    PermissionFactory,
    RoleFactory,
    StockEntryDetailFactory,
    StockEntryFactory,
    StockLedgerFactory,
    UserFactory,
    WarehouseFactory,
    WorkOrderFactory,
)


@pytest.mark.django_db
class TestStockInAPI:
    """Test suite cho Stock In API endpoints."""

    @pytest.fixture
    def setup_data(self):
        """Setup data cho test."""
        warehouse = WarehouseFactory()
        item = ItemFactory()
        return {"warehouse": warehouse, "item": item}

    def test_stock_in_create_success(self, authenticated_api_client, setup_data):
        """Test tạo phiếu nhập kho qua API."""
        data = setup_data

        payload = {
            "name": "SI-2024-001",
            "posting_date": datetime.now().isoformat(),
            "remarks": "Nhập kho",
            "details": [
                {
                    "item_id": str(data["item"].id),
                    "quantity": "100.00",
                    "target_warehouse_id": str(data["warehouse"].id),
                }
            ],
        }

        response = authenticated_api_client.post(
            "/api/v1/inventory/stock-in/create/",
            data=payload,
            format="json",
        )

        assert response.status_code == 201
        assert response.data["name"] == "SI-2024-001"
        assert response.data["status"] == "draft"

    def test_stock_in_create_no_auth(self, api_client, setup_data):
        """Test tạo phiếu nhập kho mà không xác thực."""
        data = setup_data

        payload = {
            "name": "SI-2024-001",
            "posting_date": datetime.now().isoformat(),
            "details": [
                {
                    "item_id": str(data["item"].id),
                    "quantity": "100.00",
                    "target_warehouse_id": str(data["warehouse"].id),
                }
            ],
        }

        response = api_client.post(
            "/api/v1/inventory/stock-in/create/",
            data=payload,
            format="json",
        )

        assert response.status_code == 401

    def test_stock_in_create_no_permission(self, api_client, setup_data):
        """Test tạo phiếu nhập kho mà không có quyền."""
        user = UserFactory(role=RoleFactory())
        api_client.force_authenticate(user=user)
        data = setup_data

        payload = {
            "name": "SI-2024-001",
            "posting_date": datetime.now().isoformat(),
            "details": [
                {
                    "item_id": str(data["item"].id),
                    "quantity": "100.00",
                    "target_warehouse_id": str(data["warehouse"].id),
                }
            ],
        }

        response = api_client.post(
            "/api/v1/inventory/stock-in/create/",
            data=payload,
            format="json",
        )

        assert response.status_code == 403

    def test_stock_in_create_invalid_data(self, authenticated_api_client):
        """Test tạo phiếu nhập kho với dữ liệu không hợp lệ."""

        payload = {
            "name": "SI-2024-001",
            "posting_date": datetime.now().isoformat(),
            "details": [],  # Không có chi tiết
        }

        response = authenticated_api_client.post(
            "/api/v1/inventory/stock-in/create/",
            data=payload,
            format="json",
        )

        assert response.status_code == 400

    def test_stock_in_approve_success(self, authenticated_api_client):
        """Test phê duyệt phiếu nhập kho qua API."""
        entry = StockEntryFactory(purpose="receipt", status="draft")

        response = authenticated_api_client.post(
            f"/api/v1/inventory/stock-in/{entry.id}/approve/",
        )

        assert response.status_code == 200
        assert response.data["status"] == "posted"


@pytest.mark.django_db
class TestStockIssueAPI:
    """Test suite cho Stock Issue API endpoints."""

    def test_stock_issue_create_success(self, authenticated_api_client):
        """Test tạo phiếu xuất kho cho sản xuất qua API."""

        # Setup
        warehouse = WarehouseFactory()
        main_item = ItemFactory()
        material = ItemFactory()

        bom = BOMFactory(item=main_item)
        BOMItemFactory(parent=bom, item=material, quantity=Decimal("5.00"))

        work_order = WorkOrderFactory(production_item=main_item, quantity=10)
        StockLedgerFactory(item=material, warehouse=warehouse, actual_quantity=Decimal("100.00"))

        payload = {
            "name": "SO-2024-001",
            "posting_date": datetime.now().isoformat(),
            "source_warehouse_id": str(warehouse.id),
            "details": [
                {
                    "item_id": str(material.id),
                    "quantity": "50.00",
                }
            ],
        }

        response = authenticated_api_client.post(
            "/api/v1/inventory/stock-issue/create/",
            data=payload,
            format="json",
        )

        assert response.status_code == 201
        assert response.data["purpose"] == "issue"


@pytest.mark.django_db
class TestStockTransferAPI:
    """Test suite cho Stock Transfer API endpoints."""

    def test_stock_transfer_create_success(self, authenticated_api_client):
        """Test tạo phiếu chuyển kho qua API."""

        # Setup
        warehouse1 = WarehouseFactory()
        warehouse2 = WarehouseFactory()
        item = ItemFactory()

        StockLedgerFactory(item=item, warehouse=warehouse1, actual_quantity=Decimal("100.00"))

        payload = {
            "name": "ST-2024-001",
            "posting_date": datetime.now().isoformat(),
            "source_warehouse_id": str(warehouse1.id),
            "target_warehouse_id": str(warehouse2.id),
            "details": [
                {
                    "item_id": str(item.id),
                    "quantity": "50.00",
                }
            ],
        }

        response = authenticated_api_client.post(
            "/api/v1/inventory/stock-transfer/create/",
            data=payload,
            format="json",
        )

        assert response.status_code == 201
        assert response.data["purpose"] == "transfer"


@pytest.mark.django_db
class TestStockLedgerAPI:
    """Test suite cho Stock Ledger Query API endpoints."""

    def test_stock_ledger_balance_success(self, authenticated_api_client):
        """Test lấy tồn kho của warehouse qua API."""

        # Setup
        warehouse = WarehouseFactory()
        item1 = ItemFactory()
        item2 = ItemFactory()

        StockLedgerFactory(item=item1, warehouse=warehouse, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=item2, warehouse=warehouse, actual_quantity=Decimal("50.00"))

        response = authenticated_api_client.get(
            f"/api/v1/inventory/stock-ledger/balance/?warehouse_id={warehouse.id}",
        )

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_stock_ledger_balance_no_warehouse_id_success(self, authenticated_api_client):
        """Test lấy tồn kho của tất cả warehouse qua API (warehouse_id optional)."""

        # Setup
        warehouse1 = WarehouseFactory()
        warehouse2 = WarehouseFactory()
        item1 = ItemFactory()

        StockLedgerFactory(item=item1, warehouse=warehouse1, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=item1, warehouse=warehouse2, actual_quantity=Decimal("50.00"))

        response = authenticated_api_client.get(
            "/api/v1/inventory/stock-ledger/balance/",
        )

        assert response.status_code == 200
        assert len(response.data) == 1
        assert Decimal(response.data[0]["total_quantity"]) == Decimal("150.00")

    def test_stock_ledger_balance_detailed_success(self, authenticated_api_client):
        """Test lấy tồn kho phân rã chi tiết theo từng kho (detailed=true) qua API."""

        # Setup
        warehouse1 = WarehouseFactory()
        warehouse2 = WarehouseFactory()
        item1 = ItemFactory()
        item2 = ItemFactory()

        StockLedgerFactory(item=item1, warehouse=warehouse1, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=item1, warehouse=warehouse2, actual_quantity=Decimal("50.00"))
        StockLedgerFactory(item=item2, warehouse=warehouse1, actual_quantity=Decimal("0.00"))

        response = authenticated_api_client.get(
            "/api/v1/inventory/stock-ledger/balance/?detailed=true",
        )

        assert response.status_code == 200
        # Should return 2 records since item2 has 0 balance and is filtered out
        assert len(response.data) == 2

        # Verify warehouse_id is populated
        for record in response.data:
            assert record["warehouse_id"] is not None
            assert str(record["item_id"]) == str(item1.id)

    def test_stock_ledger_balance_no_auth(self, api_client):
        """Test lấy tồn kho mà không xác thực."""
        warehouse = WarehouseFactory()

        response = api_client.get(
            f"/api/v1/inventory/stock-ledger/balance/?warehouse_id={warehouse.id}",
        )

        assert response.status_code == 401

    def test_stock_entry_list_success(self, authenticated_api_client):
        """Test lấy danh sách phiếu stock entry qua API."""

        # Setup
        StockEntryFactory(status="draft", purpose="receipt")
        StockEntryFactory(status="draft", purpose="receipt")

        response = authenticated_api_client.get(
            "/api/v1/inventory/stock-entry/list/?status=draft",
        )

        assert response.status_code == 200
        assert "count" in response.data
        assert "results" in response.data
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_stock_entry_list_with_filter(self, authenticated_api_client):
        """Test lấy danh sách phiếu stock entry với filter mục đích."""

        # Setup
        StockEntryFactory(status="draft", purpose="receipt")
        StockEntryFactory(status="draft", purpose="issue")

        response = authenticated_api_client.get(
            "/api/v1/inventory/stock-entry/list/?status=draft&purpose=receipt",
        )

        assert response.status_code == 200
        assert "count" in response.data
        assert "results" in response.data
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
