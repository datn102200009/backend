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
    def client(self):
        """API client."""
        return APIClient()

    @pytest.fixture
    def user_with_permission(self):
        """User với quyền stock_in."""
        role = RoleFactory(name="Thủ kho")
        perm = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role, username="warehousekeeper")
        return user

    @pytest.fixture
    def setup_data(self):
        """Setup data cho test."""
        warehouse = WarehouseFactory()
        item = ItemFactory()
        return {"warehouse": warehouse, "item": item}

    def test_stock_in_create_success(self, client, user_with_permission, setup_data):
        """Test tạo phiếu nhập kho qua API."""
        client.force_authenticate(user=user_with_permission)
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

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 201
        assert response.data["name"] == "SI-2024-001"
        assert response.data["status"] == "draft"

    def test_stock_in_create_no_auth(self, client, setup_data):
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

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_stock_in_create_no_permission(self, client, setup_data):
        """Test tạo phiếu nhập kho mà không có quyền."""
        user = UserFactory(role=RoleFactory())
        client.force_authenticate(user=user)
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

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 403

    def test_stock_in_create_invalid_data(self, client, user_with_permission):
        """Test tạo phiếu nhập kho với dữ liệu không hợp lệ."""
        client.force_authenticate(user=user_with_permission)

        payload = {
            "name": "SI-2024-001",
            "posting_date": datetime.now().isoformat(),
            "details": [],  # Không có chi tiết
        }

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_stock_in_approve_success(self, client, user_with_permission):
        """Test phê duyệt phiếu nhập kho qua API."""
        # Setup quyền approve
        perm_approve = PermissionFactory(code="inventory.stock_in_approve")
        RolePermission.objects.create(
            role=user_with_permission.role,
            permission=perm_approve,
        )

        client.force_authenticate(user=user_with_permission)
        entry = StockEntryFactory(purpose="receipt", status="draft")

        response = client.post(
            f"/api/v1/inventory/stock-in/{entry.id}/approve/",
        )

        assert response.status_code == 200
        assert response.data["status"] == "posted"


@pytest.mark.django_db
class TestStockIssueAPI:
    """Test suite cho Stock Issue API endpoints."""

    @pytest.fixture
    def client(self):
        """API client."""
        return APIClient()

    @pytest.fixture
    def user_with_permission(self):
        """User với quyền stock_issue."""
        role = RoleFactory(name="Thủ kho")
        perm = PermissionFactory(code="inventory.stock_issue")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role)
        return user

    def test_stock_issue_create_success(self, client, user_with_permission):
        """Test tạo phiếu xuất kho cho sản xuất qua API."""
        client.force_authenticate(user=user_with_permission)

        # Setup
        warehouse = WarehouseFactory()
        main_item = ItemFactory()
        material = ItemFactory()

        bom = BOMFactory(item=main_item)
        BOMItemFactory(bom=bom, item=material, qty=Decimal("5.00"))

        work_order = WorkOrderFactory(item=main_item, qty=Decimal("10.00"))
        StockLedgerFactory(item=material, warehouse=warehouse, actual_quantity=Decimal("100.00"))

        payload = {
            "name": "SO-2024-001",
            "posting_date": datetime.now().isoformat(),
            "work_order_id": str(work_order.id),
            "source_warehouse_id": str(warehouse.id),
        }

        response = client.post(
            "/api/v1/inventory/stock-issue/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 201
        assert response.data["purpose"] == "issue"


@pytest.mark.django_db
class TestStockTransferAPI:
    """Test suite cho Stock Transfer API endpoints."""

    @pytest.fixture
    def client(self):
        """API client."""
        return APIClient()

    @pytest.fixture
    def user_with_permission(self):
        """User với quyền stock_transfer."""
        role = RoleFactory(name="Thủ kho")
        perm = PermissionFactory(code="inventory.stock_transfer")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role)
        return user

    def test_stock_transfer_create_success(self, client, user_with_permission):
        """Test tạo phiếu chuyển kho qua API."""
        client.force_authenticate(user=user_with_permission)

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

        response = client.post(
            "/api/v1/inventory/stock-transfer/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 201
        assert response.data["purpose"] == "transfer"


@pytest.mark.django_db
class TestStockLedgerAPI:
    """Test suite cho Stock Ledger Query API endpoints."""

    @pytest.fixture
    def client(self):
        """API client."""
        return APIClient()

    @pytest.fixture
    def user_with_permission(self):
        """User với quyền xem tồn kho."""
        role = RoleFactory(name="Nhân viên")
        perm = PermissionFactory(code="inventory.view")
        RolePermission.objects.create(role=role, permission=perm)
        user = UserFactory(role=role)
        return user

    def test_stock_ledger_balance_success(self, client, user_with_permission):
        """Test lấy tồn kho của warehouse qua API."""
        client.force_authenticate(user=user_with_permission)

        # Setup
        warehouse = WarehouseFactory()
        item1 = ItemFactory()
        item2 = ItemFactory()

        StockLedgerFactory(item=item1, warehouse=warehouse, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=item2, warehouse=warehouse, actual_quantity=Decimal("50.00"))

        response = client.get(
            f"/api/v1/inventory/stock-ledger/balance/?warehouse_id={warehouse.id}",
        )

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_stock_ledger_balance_no_auth(self, client):
        """Test lấy tồn kho mà không xác thực."""
        warehouse = WarehouseFactory()

        response = client.get(
            f"/api/v1/inventory/stock-ledger/balance/?warehouse_id={warehouse.id}",
        )

        assert response.status_code == 401

    def test_stock_entry_list_success(self, client, user_with_permission):
        """Test lấy danh sách phiếu stock entry qua API."""
        client.force_authenticate(user=user_with_permission)

        # Setup
        StockEntryFactory(status="draft", purpose="receipt")
        StockEntryFactory(status="draft", purpose="receipt")

        response = client.get(
            "/api/v1/inventory/stock-entry/list/?status=draft",
        )

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_stock_entry_list_with_filter(self, client, user_with_permission):
        """Test lấy danh sách phiếu stock entry với filter mục đích."""
        client.force_authenticate(user=user_with_permission)

        # Setup
        StockEntryFactory(status="draft", purpose="receipt")
        StockEntryFactory(status="draft", purpose="issue")

        response = client.get(
            "/api/v1/inventory/stock-entry/list/?status=draft&purpose=receipt",
        )

        assert response.status_code == 200
        assert len(response.data) == 1
