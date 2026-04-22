"""
API Contract Tests - Schema & Response Structure Validation.

Kiểm tra schema của API responses phải đúng định dạng.
"""

import json
from datetime import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import RolePermission
from apps.inventory.models import StockEntry
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
class TestStockInAPIContract:
    """Test API contract cho Stock In endpoints."""

    @pytest.fixture
    def setup(self):
        """Setup user, warehouse, items."""
        role = RoleFactory()
        for code in ["inventory.stock_in", "inventory.stock_in_approve", "inventory.view"]:
            perm = PermissionFactory(code=code)
            RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)
        warehouse = WarehouseFactory()
        item = ItemFactory()

        return {"user": user, "warehouse": warehouse, "item": item}

    def test_create_response_structure(self, setup):
        """Response create phải có structure chuẩn."""
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(
                {
                    "name": "SI-001",
                    "posting_date": datetime.now().isoformat(),
                    "details": [
                        {
                            "item_id": str(setup["item"].id),
                            "quantity": "100.00",
                            "target_warehouse_id": str(setup["warehouse"].id),
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201

        # Kiểm tra schema
        data = response.data

        # Bắt buộc có những field này
        required_fields = ["id", "name", "status", "posting_date", "details", "created_at", "remarks"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Kiểm tra type
        assert isinstance(data["id"], str)  # UUID
        assert isinstance(data["name"], str)
        assert data["status"] == "draft"
        assert isinstance(data["posting_date"], str)
        assert isinstance(data["details"], list)
        assert len(data["details"]) == 1

        # Kiểm tra detail structure
        detail = data["details"][0]
        detail_fields = ["id", "item_id", "item_code", "quantity", "target_warehouse_id"]
        for field in detail_fields:
            assert field in detail, f"Missing detail field: {field}"

        assert isinstance(detail["quantity"], str)
        assert detail["quantity"] == "100.00"

    def test_approve_response_structure(self, setup):
        """Response approve phải có structure chuẩn."""
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        # Create trước
        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(
                {
                    "name": "SI-APPROVE",
                    "posting_date": datetime.now().isoformat(),
                    "details": [
                        {
                            "item_id": str(setup["item"].id),
                            "quantity": "100.00",
                            "target_warehouse_id": str(setup["warehouse"].id),
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        entry_id = response.data["id"]

        # Approve
        response = client.post(
            f"/api/v1/inventory/stock-in/{entry_id}/approve/",
        )

        assert response.status_code == 200

        # Kiểm tra schema
        data = response.data
        assert data["status"] == "posted"
        assert data["id"] == entry_id
        assert "updated_at" in data or "modified_at" in data


@pytest.mark.django_db
class TestStockLedgerAPIContract:
    """Test API contract cho Stock Ledger endpoints."""

    def test_balance_endpoint_response_structure(self):
        """GET balance endpoint phải trả về structure chuẩn."""
        role = RoleFactory()
        perm = PermissionFactory(code="inventory.view")
        RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)
        warehouse = WarehouseFactory()
        item1 = ItemFactory()
        item2 = ItemFactory()

        # Tạo tồn kho
        StockLedgerFactory(item=item1, warehouse=warehouse, actual_quantity=Decimal("100.00"))
        StockLedgerFactory(item=item2, warehouse=warehouse, actual_quantity=Decimal("50.00"))

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(
            f"/api/v1/inventory/stock-ledger/balance/?warehouse_id={warehouse.id}",
        )

        assert response.status_code == 200

        # Response phải là list
        assert isinstance(response.data, list)
        assert len(response.data) == 2

        # Mỗi item phải có structure
        for item_balance in response.data:
            required_fields = ["item_id", "item_code", "item_name", "total_quantity", "uom"]
            for field in required_fields:
                assert field in item_balance, f"Missing field: {field}"

            assert isinstance(item_balance["total_quantity"], (int, float, str, Decimal))

    def test_list_endpoint_response_structure(self):
        """GET list endpoint phải trả về structure chuẩn."""
        role = RoleFactory()
        perm = PermissionFactory(code="inventory.view")
        RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/v1/inventory/stock-entry/list/")

        assert response.status_code == 200

        # Response structure
        assert isinstance(response.data, list)

        # Nếu có data
        if len(response.data) > 0:
            entry = response.data[0]
            required_fields = ["id", "name", "status", "posting_date"]
            for field in required_fields:
                assert field in entry, f"Missing field in entry: {field}"


@pytest.mark.django_db
class TestErrorResponseContract:
    """Test API contract cho error responses."""

    def test_404_response_structure(self):
        """404 error phải có structure chuẩn."""
        role = RoleFactory()
        perm = PermissionFactory(code="inventory.stock_in_approve")
        RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)

        client = APIClient()
        client.force_authenticate(user=user)

        # Try approve non-existent entry
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/api/v1/inventory/stock-in/{fake_id}/approve/",
        )

        assert response.status_code == 404

        # Error response structure
        assert "error" in response.data or "detail" in response.data

    def test_400_validation_error_structure(self):
        """400 validation error phải có structure chuẩn."""
        role = RoleFactory()
        perm = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)

        client = APIClient()
        client.force_authenticate(user=user)

        # Invalid data
        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(
                {
                    "name": "",  # Empty name
                    "posting_date": datetime.now().isoformat(),
                    "details": [],  # No details
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400

        # Error response phải có chi tiết lỗi
        assert "error" in response.data or len(response.data) > 0

    def test_403_permission_error_structure(self):
        """403 permission error phải có structure chuẩn."""
        user = UserFactory(role=RoleFactory())  # No permissions

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps({"name": "SI-001"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        assert "error" in response.data or "detail" in response.data


@pytest.mark.django_db
class TestDataTypeConsistency:
    """Test consistency của data types trong responses."""

    def test_quantity_as_string_not_float(self):
        """Quantity phải là string để tránh floating-point precision issues."""
        role = RoleFactory()
        for code in ["inventory.stock_in", "inventory.view"]:
            perm = PermissionFactory(code=code)
            RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)
        warehouse = WarehouseFactory()
        item = ItemFactory()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(
                {
                    "name": "SI-QUANTITY-TEST",
                    "posting_date": datetime.now().isoformat(),
                    "details": [
                        {
                            "item_id": str(item.id),
                            "quantity": "123.45",
                            "target_warehouse_id": str(warehouse.id),
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201

        # Quantity phải là string
        detail = response.data["details"][0]
        assert isinstance(detail["quantity"], str)
        assert detail["quantity"] == "123.45"

    def test_ids_as_strings(self):
        """IDs phải là string (UUID format)."""
        role = RoleFactory()
        perm = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)
        warehouse = WarehouseFactory()
        item = ItemFactory()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            "/api/v1/inventory/stock-in/create/",
            data=json.dumps(
                {
                    "name": "SI-ID-TEST",
                    "posting_date": datetime.now().isoformat(),
                    "details": [
                        {
                            "item_id": str(item.id),
                            "quantity": "100.00",
                            "target_warehouse_id": str(warehouse.id),
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201

        # IDs phải là string
        assert isinstance(response.data["id"], str)
        detail = response.data["details"][0]
        assert isinstance(detail["item_id"], str)


@pytest.mark.django_db
class TestStockTransferContractWithDoubleTransaction:
    """Test contract của stock transfer response with double transaction."""

    def test_transfer_response_includes_transaction_info(self):
        """Stock transfer response phải có thông tin về double transaction."""
        role = RoleFactory()
        for code in ["inventory.stock_transfer", "inventory.stock_transfer_approve"]:
            perm = PermissionFactory(code=code)
            RolePermission.objects.create(role=role, permission=perm)

        user = UserFactory(role=role)
        w1 = WarehouseFactory(name="W1")
        w2 = WarehouseFactory(name="W2")
        item = ItemFactory()

        # Setup initial stock
        StockLedgerFactory(item=item, warehouse=w1, actual_quantity=Decimal("100.00"))

        client = APIClient()
        client.force_authenticate(user=user)

        # Create transfer
        response = client.post(
            "/api/v1/inventory/stock-transfer/create/",
            data=json.dumps(
                {
                    "name": "ST-CONTRACT",
                    "posting_date": datetime.now().isoformat(),
                    "source_warehouse_id": str(w1.id),
                    "target_warehouse_id": str(w2.id),
                    "details": [
                        {
                            "item_id": str(item.id),
                            "quantity": "50.00",
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        entry_id = response.data["id"]

        # Approve - triggers double transaction
        response = client.post(
            f"/api/v1/inventory/stock-transfer/{entry_id}/approve/",
        )

        assert response.status_code == 200

        # Response phải indicate success
        assert response.data["status"] == "posted"
