from decimal import Decimal

import pytest

from apps.common.xlib.exceptions import PermissionException
from apps.manufacturing.services import bom_create, bom_delete, bom_update, work_order_complete, work_order_create


@pytest.mark.django_db
class TestManufacturingPermissions:
    def test_bom_create_permission(self, regular_user):
        with pytest.raises(PermissionException, match="Người dùng không có quyền:"):
            bom_create(user=regular_user, name="Test", item_id="123", items=[])

    def test_bom_update_permission(self, regular_user):
        with pytest.raises(PermissionException, match="Người dùng không có quyền:"):
            bom_update(
                user=regular_user,
                bom_id="123",
            )

    def test_bom_delete_permission(self, regular_user):
        with pytest.raises(PermissionException, match="Người dùng không có quyền:"):
            bom_delete(
                user=regular_user,
                bom_id="123",
            )

    def test_work_order_create_permission(self, regular_user):
        with pytest.raises(PermissionException, match="Người dùng không có quyền:"):
            work_order_create(
                user=regular_user,
                name="Test",
                bom_id="123",
                quantity=10,
                source_warehouse_id="123",
                target_warehouse_id="123",
                production_warehouse_id="123",
                planned_start_date="2024-01-01",
            )

    def test_work_order_complete_permission(self, regular_user):
        with pytest.raises(PermissionException, match="Người dùng không có quyền:"):
            work_order_complete(
                user=regular_user,
                work_order_id="123",
            )
