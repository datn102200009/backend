from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.xlib.exceptions import ValidationException
from apps.finance.models import FixedAsset
from apps.finance.selectors import fixed_asset_list
from apps.finance.tests.factories import FixedAssetFactory
from apps.inventory.models import StockLedger
from apps.inventory.tests.factories import BOMFactory, BOMItemFactory, ItemFactory, UserFactory, WarehouseFactory
from apps.manufacturing.services import work_order_approve, work_order_complete, work_order_set_fixed_assets
from apps.master_data.models import WorkOrder, WorkOrderFixedAsset

pytestmark = pytest.mark.django_db


class TestWorkOrderHook:
    @pytest.fixture
    def user(self):
        return UserFactory()

    @pytest.fixture
    def setup_wo_and_assets(self, user):
        # 1. Setup item and BOM
        item = ItemFactory()
        bom = BOMFactory(item=item, is_active=True)
        component = ItemFactory()
        BOMItemFactory(parent=bom, item=component, quantity=Decimal("1.00"))

        # 2. Setup warehouses and stock
        source_wh = WarehouseFactory()
        production_wh = WarehouseFactory()
        target_wh = WarehouseFactory()

        StockLedger.objects.create(
            item=component,
            warehouse=source_wh,
            actual_quantity=Decimal("100.00"),
            posting_date=timezone.now(),
            voucher_number="VOUCHER-STOCK-INIT",
            voucher_type="Stock Adjustment",
        )

        # 3. Create WorkOrder
        from apps.inventory.tests.factories import WorkOrderFactory

        work_order = WorkOrder.objects.create(
            name="WO-HOOK-TEST",
            bom=bom,
            production_item=item,
            quantity=Decimal("10.00"),
            source_warehouse=source_wh,
            target_warehouse=target_wh,
            production_warehouse=production_wh,
            status="pending_approval",
            planned_start_date=timezone.now().date(),
        )

        # 4. Create assets
        asset_idle = FixedAssetFactory(status="idle", depreciation_method="unit_of_production")
        asset_pending = FixedAssetFactory(status="pending_receive", depreciation_method="unit_of_production")
        asset_dispose = FixedAssetFactory(status="pending_dispose", depreciation_method="unit_of_production")

        return {
            "work_order": work_order,
            "asset_idle": asset_idle,
            "asset_pending": asset_pending,
            "asset_dispose": asset_dispose,
        }

    def test_wo_in_progress_sets_asset_active(self, user, setup_wo_and_assets):
        wo = setup_wo_and_assets["work_order"]
        asset = setup_wo_and_assets["asset_idle"]

        # Assign asset to WO
        work_order_set_fixed_assets(
            user=user, work_order_id=str(wo.id), fixed_asset_ids=[str(asset.id)], check_perm=False
        )
        assert asset.status == "idle"

        # Approve WO -> transitions to in_progress and sets asset active
        approved = work_order_approve(user=user, work_order_id=str(wo.id))
        assert approved.status == "in_progress"

        asset.refresh_from_db()
        assert asset.status == "active"

    def test_wo_completed_sets_asset_idle(self, user, setup_wo_and_assets):
        wo = setup_wo_and_assets["work_order"]
        asset = setup_wo_and_assets["asset_idle"]

        work_order_set_fixed_assets(
            user=user, work_order_id=str(wo.id), fixed_asset_ids=[str(asset.id)], check_perm=False
        )

        # Approve WO -> in_progress
        wo = work_order_approve(user=user, work_order_id=str(wo.id))

        asset.refresh_from_db()
        assert asset.status == "active"

        # Declare produced qty (needed for completion check)
        wo.produced_qty = Decimal("10.00")
        wo.save()

        # Complete WO -> transitions to completed and sets asset idle
        completed = work_order_complete(user=user, work_order_id=str(wo.id))
        assert completed.status == "completed"

        asset.refresh_from_db()
        assert asset.status == "idle"

    def test_wo_in_progress_blocks_when_asset_not_idle(self, user, setup_wo_and_assets):
        wo = setup_wo_and_assets["work_order"]
        asset_pending = setup_wo_and_assets["asset_pending"]

        # Try to assign asset_pending directly. It should fail validation in work_order_set_fixed_assets because status is not idle.
        with pytest.raises(ValidationException, match="phải ở trạng thái nhàn rỗi"):
            work_order_set_fixed_assets(
                user=user, work_order_id=str(wo.id), fixed_asset_ids=[str(asset_pending.id)], check_perm=False
            )

        # Bypass work_order_set_fixed_assets to simulate race condition where asset changes status after assignment
        asset_idle = setup_wo_and_assets["asset_idle"]
        work_order_set_fixed_assets(
            user=user, work_order_id=str(wo.id), fixed_asset_ids=[str(asset_idle.id)], check_perm=False
        )

        # Manually change asset to pending_receive to trigger the validate_fixed_assets_for_workorder_start error on approve
        asset_idle.status = "pending_receive"
        asset_idle.save()

        # Approve WO should now fail validation
        with pytest.raises(ValidationException, match="chưa ở trạng thái 'idle'"):
            work_order_approve(user=user, work_order_id=str(wo.id))

        # Check WO remains pending_approval
        wo.refresh_from_db()
        assert wo.status == "pending_approval"

    def test_assignable_endpoint_returns_only_idle(self, setup_wo_and_assets):
        # Get list with status_filter = ["idle"]
        qs = fixed_asset_list(status_filter=["idle"])
        assert qs.count() == 1
        assert qs.first().status == "idle"
