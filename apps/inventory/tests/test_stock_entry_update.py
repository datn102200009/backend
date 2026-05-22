import json

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import RolePermission
from apps.common.xlib.exceptions import PermissionException
from apps.inventory.services import stock_entry_update
from apps.inventory.tests.factories import (
    PermissionFactory,
    RoleFactory,
    StockEntryDetailFactory,
    StockEntryFactory,
    UserFactory,
    WarehouseFactory,
)


@pytest.mark.django_db
class TestStockEntryUpdatePermissions:
    """Test suite cho phân quyền cập nhật phiếu kho theo loại phiếu (receipt, issue, transfer)."""

    @pytest.fixture
    def setup_users(self):
        # Tạo các vai trò
        role_receipt = RoleFactory(name="Thủ kho Nhập")
        role_issue = RoleFactory(name="Thủ kho Xuất")
        role_transfer = RoleFactory(name="Thủ kho Chuyển")
        role_none = RoleFactory(name="Nhân viên thường")

        # Gán quyền tương ứng
        perm_receipt = PermissionFactory(code="inventory.stock_in")
        perm_issue = PermissionFactory(code="inventory.stock_issue")
        perm_transfer = PermissionFactory(code="inventory.stock_transfer")

        RolePermission.objects.create(role=role_receipt, permission=perm_receipt)
        RolePermission.objects.create(role=role_issue, permission=perm_issue)
        RolePermission.objects.create(role=role_transfer, permission=perm_transfer)

        # Tạo người dùng
        user_receipt = UserFactory(role=role_receipt, username="user_receipt")
        user_issue = UserFactory(role=role_issue, username="user_issue")
        user_transfer = UserFactory(role=role_transfer, username="user_transfer")
        user_none = UserFactory(role=role_none, username="user_none")

        return {
            "receipt": user_receipt,
            "issue": user_issue,
            "transfer": user_transfer,
            "none": user_none,
        }

    def test_service_update_receipt_permission(self, setup_users):
        """Hàm update với phiếu receipt yêu cầu quyền inventory.stock_in."""
        entry = StockEntryFactory(purpose="receipt", status="draft")
        detail = StockEntryDetailFactory(parent=entry)
        warehouse = WarehouseFactory()

        details_payload = [
            {
                "detail_id": detail.id,
                "source_warehouse_id": None,
                "target_warehouse_id": warehouse.id,
            }
        ]

        # User có quyền receipt (inventory.stock_in) cập nhật thành công
        stock_entry_update(
            user=setup_users["receipt"],
            stock_entry_id=str(entry.id),
            details=details_payload,
        )

        # User không có quyền bị từ chối
        with pytest.raises(PermissionException) as exc:
            stock_entry_update(
                user=setup_users["issue"],
                stock_entry_id=str(entry.id),
                details=details_payload,
            )
        assert "không có quyền" in str(exc.value)

    def test_service_update_issue_permission(self, setup_users):
        """Hàm update với phiếu issue yêu cầu quyền inventory.stock_issue."""
        entry = StockEntryFactory(purpose="issue", status="draft")
        detail = StockEntryDetailFactory(parent=entry)
        warehouse = WarehouseFactory()

        details_payload = [
            {
                "detail_id": detail.id,
                "source_warehouse_id": warehouse.id,
                "target_warehouse_id": None,
            }
        ]

        # User có quyền issue (inventory.stock_issue) cập nhật thành công
        stock_entry_update(
            user=setup_users["issue"],
            stock_entry_id=str(entry.id),
            details=details_payload,
        )

        # User không có quyền bị từ chối
        with pytest.raises(PermissionException) as exc:
            stock_entry_update(
                user=setup_users["receipt"],
                stock_entry_id=str(entry.id),
                details=details_payload,
            )
        assert "không có quyền" in str(exc.value)

    def test_service_update_transfer_permission(self, setup_users):
        """Hàm update với phiếu transfer yêu cầu quyền inventory.stock_transfer."""
        entry = StockEntryFactory(purpose="transfer", status="draft")
        detail = StockEntryDetailFactory(parent=entry)
        warehouse_src = WarehouseFactory()
        warehouse_tgt = WarehouseFactory()

        details_payload = [
            {
                "detail_id": detail.id,
                "source_warehouse_id": warehouse_src.id,
                "target_warehouse_id": warehouse_tgt.id,
            }
        ]

        # User có quyền transfer (inventory.stock_transfer) cập nhật thành công
        stock_entry_update(
            user=setup_users["transfer"],
            stock_entry_id=str(entry.id),
            details=details_payload,
        )

        # User không có quyền bị từ chối
        with pytest.raises(PermissionException) as exc:
            stock_entry_update(
                user=setup_users["receipt"],
                stock_entry_id=str(entry.id),
                details=details_payload,
            )
        assert "không có quyền" in str(exc.value)

    def test_service_update_fallback_permission(self, setup_users):
        """Hàm update với phiếu purpose khác yêu cầu quyền fallback (inventory.stock_in)."""
        entry = StockEntryFactory(purpose="other_purpose", status="draft")
        detail = StockEntryDetailFactory(parent=entry)
        warehouse = WarehouseFactory()

        details_payload = [
            {
                "detail_id": detail.id,
                "source_warehouse_id": None,
                "target_warehouse_id": warehouse.id,
            }
        ]

        # Yêu cầu quyền fallback là inventory.stock_in
        stock_entry_update(
            user=setup_users["receipt"],
            stock_entry_id=str(entry.id),
            details=details_payload,
        )

        with pytest.raises(PermissionException):
            stock_entry_update(
                user=setup_users["issue"],
                stock_entry_id=str(entry.id),
                details=details_payload,
            )

    def test_api_view_update_permissions(self, setup_users):
        """Kiểm tra phân quyền động trên API View."""
        client = APIClient()

        # 1. Phiếu issue
        entry_issue = StockEntryFactory(purpose="issue", status="draft")
        detail_issue = StockEntryDetailFactory(parent=entry_issue)
        warehouse = WarehouseFactory()

        url_issue = f"/api/v1/inventory/stock-entry/{entry_issue.id}/update/"
        payload = {
            "details": [
                {
                    "detail_id": str(detail_issue.id),
                    "source_warehouse_id": str(warehouse.id),
                    "target_warehouse_id": None,
                }
            ]
        }

        # Thử với user có quyền stock_issue -> 200 OK
        client.force_authenticate(user=setup_users["issue"])
        response = client.post(url_issue, data=payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Thử với user không có quyền stock_issue (chỉ có stock_in) -> 403 Forbidden
        client.force_authenticate(user=setup_users["receipt"])
        response = client.post(url_issue, data=payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "không có quyền" in response.data["error"]
