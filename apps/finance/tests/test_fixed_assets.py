import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.finance.models import FixedAsset, FixedAssetDepreciationLog
from apps.finance.services import (
    fixed_asset_create,
    fixed_asset_delete,
    fixed_asset_update,
    run_fixed_asset_depreciation,
)
from apps.finance.tests.factories import FixedAssetDepreciationLogFactory, FixedAssetFactory
from apps.inventory.tests.factories import (
    BOMFactory,
    BOMItemFactory,
    ItemFactory,
    StockEntryDetailFactory,
    StockEntryFactory,
    UserFactory,
    WarehouseFactory,
)

pytestmark = pytest.mark.django_db


class TestFixedAssetServices:
    @pytest.fixture
    def user(self):
        return UserFactory()

    def test_fixed_asset_create_straight_line_success(self, user):
        asset = fixed_asset_create(
            user=user,
            asset_code="MOLD-001",
            asset_name="Khuôn ép nhựa 001",
            original_value=Decimal("12000.00"),
            salvage_value=Decimal("2000.00"),
            depreciation_method="straight_line",
            useful_life_months=10,
            department="Sản xuất",
        )
        assert asset.asset_code == "MOLD-001"
        assert asset.original_value == Decimal("12000.00")
        assert asset.salvage_value == Decimal("2000.00")
        assert asset.depreciation_method == "straight_line"
        assert asset.useful_life_months == 10
        assert asset.remaining_life_months == 10
        assert asset.accumulated_depreciation == Decimal("0.00")

    def test_fixed_asset_create_uop_requires_capacity(self, user):
        with pytest.raises(ValidationException, match="Công suất thiết kế phải lớn hơn 0"):
            fixed_asset_create(
                user=user,
                asset_code="MOLD-002",
                asset_name="Khuôn ép nhựa 002",
                original_value=Decimal("10000.00"),
                depreciation_method="unit_of_production",
                useful_life_months=12,
                designed_capacity=None,
            )

    def test_fixed_asset_create_duplicate_code(self, user):
        FixedAssetFactory(asset_code="MOLD-DUP")
        with pytest.raises(ValidationException, match="Mã tài sản cố định.*đã tồn tại"):
            fixed_asset_create(
                user=user,
                asset_code="MOLD-DUP",
                asset_name="Khuôn trùng tên",
                original_value=Decimal("5000.00"),
                depreciation_method="straight_line",
                useful_life_months=12,
            )

    def test_fixed_asset_update_success(self, user):
        asset = FixedAssetFactory(asset_name="Tên cũ", department="Phòng A")
        updated = fixed_asset_update(
            user=user,
            asset_id=str(asset.id),
            asset_name="Tên mới",
            department="Phòng B",
        )
        assert updated.asset_name == "Tên mới"
        assert updated.department == "Phòng B"

    def test_fixed_asset_update_core_field_blocked_after_depreciation(self, user):
        asset = FixedAssetFactory(
            original_value=Decimal("10000.00"),
            salvage_value=Decimal("0.00"),
            useful_life_months=10,
        )
        FixedAssetDepreciationLogFactory(asset=asset, depreciation_amount=Decimal("1000.00"), period="2026-05")

        # Non-core update works
        fixed_asset_update(user=user, asset_id=str(asset.id), asset_name="Tên mới")

        # Core field update fails
        with pytest.raises(ValidationException, match="Không thể sửa nguyên giá của tài sản đã phát sinh khấu hao"):
            fixed_asset_update(user=user, asset_id=str(asset.id), original_value=Decimal("12000.00"))

    def test_fixed_asset_delete_blocked_when_has_logs(self, user):
        asset = FixedAssetFactory()
        FixedAssetDepreciationLogFactory(asset=asset)

        with pytest.raises(ValidationException, match="Không thể xóa tài sản cố định đã phát sinh lịch sử khấu hao"):
            fixed_asset_delete(user=user, asset_id=str(asset.id))

    def test_fixed_asset_delete_blocked_when_linked_to_bom(self, user):
        asset = FixedAssetFactory()
        BOMFactory(mold=asset)

        with pytest.raises(ValidationException, match="Không thể xóa tài sản cố định đang liên kết với định mức BOM"):
            fixed_asset_delete(user=user, asset_id=str(asset.id))

    def test_fixed_asset_delete_success(self, user):
        asset = FixedAssetFactory()
        fixed_asset_delete(user=user, asset_id=str(asset.id))
        assert not FixedAsset.objects.filter(id=asset.id).exists()

    def test_run_depreciation_straight_line(self, user):
        asset = FixedAssetFactory(
            original_value=Decimal("10000.00"),
            salvage_value=Decimal("2000.00"),
            depreciation_method="straight_line",
            useful_life_months=10,
            remaining_life_months=10,
            accumulated_depreciation=Decimal("0.00"),
        )

        # 10000 - 2000 = 8000 depreciable. Monthly = 800
        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 1
        assert logs[0].depreciation_amount == Decimal("800.00")
        assert logs[0].period == "2026-06"

        asset.refresh_from_db()
        assert asset.accumulated_depreciation == Decimal("800.00")
        assert asset.remaining_life_months == 9

    def test_run_depreciation_uop(self, user):
        # Setup item, asset, BOM, StockEntry
        finished_good = ItemFactory()
        mold = FixedAssetFactory(
            original_value=Decimal("6000.00"),
            salvage_value=Decimal("1000.00"),
            depreciation_method="unit_of_production",
            useful_life_months=10,
            remaining_life_months=10,
            designed_capacity=Decimal("1000.00"),  # (6000-1000)/1000 = 5 VND per unit
            accumulated_depreciation=Decimal("0.00"),
        )
        # Link mold to active BOM
        bom = BOMFactory(item=finished_good, mold=mold, is_active=True)

        # Create StockEntry in 2026-06
        # Start date: 2026-06-01, End date: 2026-07-01
        warehouse = WarehouseFactory()
        posting_date = timezone.make_aware(datetime.datetime(2026, 6, 15, 12, 0, 0))
        entry = StockEntryFactory(purpose="manufacture", status="posted", posting_date=posting_date)
        StockEntryDetailFactory(
            parent=entry, item=finished_good, quantity=Decimal("150.00"), target_warehouse=warehouse
        )

        # Run depreciation
        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 1
        # 150 units * 5 VND/unit = 750 VND
        assert logs[0].depreciation_amount == Decimal("750.00")

        mold.refresh_from_db()
        assert mold.accumulated_depreciation == Decimal("750.00")
        assert mold.remaining_life_months == 9

    def test_run_depreciation_twice_fails(self, user):
        FixedAssetFactory(
            original_value=Decimal("1000.00"),
            useful_life_months=10,
            remaining_life_months=10,
        )
        run_fixed_asset_depreciation(user=user, period="2026-06")

        with pytest.raises(ValidationException, match="đã được thực hiện hạch toán trước đó"):
            run_fixed_asset_depreciation(user=user, period="2026-06")
