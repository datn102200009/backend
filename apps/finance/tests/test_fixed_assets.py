import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.finance.models import FixedAsset, FixedAssetDepreciationLog
from apps.finance.services import (
    cash_flow_approve,
    cash_flow_reject,
    fixed_asset_create,
    fixed_asset_delete,
    fixed_asset_request_dispose,
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
        asset = FixedAssetFactory(asset_name="Tên cũ", status="idle")
        updated = fixed_asset_update(
            user=user,
            asset_id=str(asset.id),
            asset_name="Tên mới",
            useful_life_months=24,
        )
        assert updated.asset_name == "Tên mới"
        assert updated.useful_life_months == 24

    def test_fixed_asset_update_core_field_blocked(self, user):
        asset = FixedAssetFactory(status="idle")
        with pytest.raises(ValidationException, match="Chỉ được phép cập nhật các trường"):
            fixed_asset_update(user=user, asset_id=str(asset.id), original_value=Decimal("12000.00"))

    def test_fixed_asset_update_blocked_for_non_idle(self, user):
        asset = FixedAssetFactory(status="active")
        with pytest.raises(
            ValidationException, match="Chỉ được phép chỉnh sửa thông tin tài sản cố định đang ở trạng thái 'idle'"
        ):
            fixed_asset_update(user=user, asset_id=str(asset.id), asset_name="Tên mới")

    def test_fixed_asset_delete_always_blocked(self, user):
        asset = FixedAssetFactory()
        with pytest.raises(ValidationException, match="Tài sản cố định chỉ có thể thanh lý, không thể xóa"):
            fixed_asset_delete(user=user, asset_id=str(asset.id))

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
            useful_life_months=None,
            remaining_life_months=None,
            designed_capacity=Decimal("1000.00"),  # (6000-1000)/1000 = 5 VND per unit
            accumulated_depreciation=Decimal("0.00"),
        )
        # Link mold to active BOM (without mold FK) and create WorkOrder linked to mold
        bom = BOMFactory(item=finished_good, is_active=True)
        from apps.inventory.tests.factories import WorkOrderFactory
        from apps.master_data.models import WorkOrderFixedAsset

        work_order = WorkOrderFactory(bom=bom, status="in_progress")
        WorkOrderFixedAsset.objects.create(work_order=work_order, fixed_asset=mold)

        # Create StockEntry in 2026-06 linked to work_order
        warehouse = WarehouseFactory()
        posting_date = timezone.make_aware(datetime.datetime(2026, 6, 15, 12, 0, 0))
        entry = StockEntryFactory(
            purpose="manufacture", status="posted", posting_date=posting_date, work_order=work_order
        )
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
        assert mold.remaining_life_months is None

    def test_run_depreciation_twice_fails(self, user):
        FixedAssetFactory(
            original_value=Decimal("1000.00"),
            useful_life_months=10,
            remaining_life_months=10,
        )
        run_fixed_asset_depreciation(user=user, period="2026-06")

        with pytest.raises(ValidationException, match="đã được thực hiện hạch toán trước đó"):
            run_fixed_asset_depreciation(user=user, period="2026-06")

    def test_run_depreciation_lock_conflict(self, user):
        from unittest.mock import patch

        from django.db import OperationalError

        FixedAssetFactory(
            original_value=Decimal("1000.00"),
            useful_life_months=10,
            remaining_life_months=10,
        )

        with patch("django.db.models.query.QuerySet.select_for_update") as mock_select:
            mock_select.side_effect = OperationalError("could not obtain lock")

            with pytest.raises(ValidationException, match="Hệ thống đang xử lý khấu hao, vui lòng thử lại sau."):
                run_fixed_asset_depreciation(user=user, period="2026-06")

    def test_fixed_asset_create_pending_receive(self, user):
        from apps.finance.models import CashFlowTransaction
        from apps.purchasing.models import PurchaseInvoice, PurchaseOrder

        # Create a placeholder item first
        ItemFactory(item_code="FA_PLACEHOLDER")

        asset = fixed_asset_create(
            user=user,
            asset_name="Test Asset",
            original_value=Decimal("1000.00"),
            depreciation_method="straight_line",
            useful_life_months=12,
            vendor_name="Test Supplier",
            payment_method="bank_transfer",
        )
        assert asset.status == "pending_receive"
        assert asset.asset_code.startswith("FA-")
        assert asset.vendor_name == "Test Supplier"
        assert asset.payment_method == "bank_transfer"

        # Verify PO, PI, CF are automatically created
        assert PurchaseOrder.objects.filter(total_amount=Decimal("1000.00")).exists()
        assert PurchaseInvoice.objects.filter(total_amount=Decimal("1000.00")).exists()

        tx = CashFlowTransaction.objects.filter(
            amount=Decimal("1000.00"), payment_type="pay", fixed_asset=asset
        ).first()
        assert tx is not None
        assert tx.status == "pending_approval"

        # Approve the Cash Flow to set Asset to idle (hook)
        cash_flow_approve(user=user, tx_id=str(tx.id))
        asset.refresh_from_db()
        assert asset.status == "idle"

    def test_fixed_asset_request_dispose_success(self, user):
        from apps.finance.models import CashFlowTransaction

        asset = FixedAssetFactory(status="idle")
        updated = fixed_asset_request_dispose(
            user=user,
            asset_id=str(asset.id),
            disposal_date="2026-06-15",
            disposal_value=Decimal("500.00"),
            remarks="Dispose it",
        )
        assert updated.status == "pending_dispose"
        assert updated.disposal_value == Decimal("500.00")
        assert str(updated.disposal_date) == "2026-06-15"

        # Verify Cash Flow transaction auto-created
        tx = CashFlowTransaction.objects.filter(
            amount=Decimal("500.00"), payment_type="receive", fixed_asset=updated
        ).first()
        assert tx is not None
        assert tx.status == "pending_approval"

        # Approve cash flow to auto-dispose (hook)
        cash_flow_approve(user=user, tx_id=str(tx.id))
        updated.refresh_from_db()
        assert updated.status == "disposed"

    def test_fixed_asset_request_dispose_success_zero_value(self, user):
        from apps.finance.models import CashFlowTransaction

        asset = FixedAssetFactory(status="idle")
        updated = fixed_asset_request_dispose(
            user=user,
            asset_id=str(asset.id),
            disposal_date="2026-06-15",
            disposal_value=Decimal("0.00"),
            remarks="Zero value",
        )
        assert updated.status == "disposed"
        assert updated.disposal_value == Decimal("0.00")
        assert str(updated.disposal_date) == "2026-06-15"

        # Verify no cash flow transaction created
        assert not CashFlowTransaction.objects.filter(fixed_asset=updated).exists()

    def test_fixed_asset_request_dispose_active_blocked(self, user):
        asset = FixedAssetFactory(status="active")
        with pytest.raises(ValidationException, match="Tài sản đang hoạt động không thể yêu cầu thanh lý"):
            fixed_asset_request_dispose(
                user=user,
                asset_id=str(asset.id),
                disposal_date="2026-06-15",
                disposal_value=Decimal("500.00"),
            )

    def test_cash_flow_reject_purchase_deletes_asset_and_po_pi(self, user):
        from apps.finance.models import CashFlowTransaction
        from apps.purchasing.models import PurchaseInvoice, PurchaseOrder

        ItemFactory(item_code="FA_PLACEHOLDER")

        asset = fixed_asset_create(
            user=user,
            asset_name="Test Asset Reject",
            original_value=Decimal("1500.00"),
            depreciation_method="straight_line",
            useful_life_months=12,
        )
        asset_id = str(asset.id)

        tx = CashFlowTransaction.objects.filter(
            amount=Decimal("1500.00"), payment_type="pay", fixed_asset=asset
        ).first()
        assert tx is not None
        assert tx.status == "pending_approval"

        po_id = tx.purchase_order_id
        pi_id = tx.purchase_invoice_id
        assert po_id is not None
        assert pi_id is not None

        # Reject Cash Flow
        cash_flow_reject(user=user, tx_id=str(tx.id), remarks="Không duyệt mua")

        # Verify asset is deleted
        assert not FixedAsset.objects.filter(id=asset_id).exists()

        # Verify PO and PI are deleted
        assert not PurchaseOrder.objects.filter(id=po_id).exists()
        assert not PurchaseInvoice.objects.filter(id=pi_id).exists()

        # Verify CF transaction remains but status is rejected, and PO/PI FKs are cleared
        tx.refresh_from_db()
        assert tx.status == "rejected"
        assert tx.purchase_order_id is None
        assert tx.purchase_invoice_id is None
        assert "[Từ chối] Không duyệt mua" in tx.remarks

    def test_cash_flow_reject_dispose_reverts_to_idle(self, user):
        from apps.finance.models import CashFlowTransaction

        asset = FixedAssetFactory(status="idle")
        updated = fixed_asset_request_dispose(
            user=user,
            asset_id=str(asset.id),
            disposal_date="2026-06-15",
            disposal_value=Decimal("3000.00"),
        )
        assert updated.status == "pending_dispose"

        tx = CashFlowTransaction.objects.filter(
            amount=Decimal("3000.00"), payment_type="receive", fixed_asset=updated
        ).first()
        assert tx is not None
        assert tx.status == "pending_approval"

        # Reject Cash Flow
        cash_flow_reject(user=user, tx_id=str(tx.id), remarks="Không duyệt thanh lý")

        # Verify asset status reverted to idle and disposal fields cleared
        updated.refresh_from_db()
        assert updated.status == "idle"
        assert updated.disposal_date is None
        assert updated.disposal_value is None

        # Verify CF status is rejected
        tx.refresh_from_db()
        assert tx.status == "rejected"
        assert "[Từ chối] Không duyệt thanh lý" in tx.remarks

    def test_fixed_asset_create_uop_without_life_months(self, user):
        asset = fixed_asset_create(
            user=user,
            asset_code="MOLD-UOP-1",
            asset_name="Khuôn UOP 1",
            original_value=Decimal("10000.00"),
            salvage_value=Decimal("1000.00"),
            depreciation_method="unit_of_production",
            useful_life_months=None,
            designed_capacity=Decimal("10000.00"),
        )
        assert asset.asset_code == "MOLD-UOP-1"
        assert asset.original_value == Decimal("10000.00")
        assert asset.salvage_value == Decimal("1000.00")
        assert asset.depreciation_method == "unit_of_production"
        assert asset.useful_life_months is None
        assert asset.remaining_life_months is None
        assert asset.designed_capacity == Decimal("10000.00")

    def test_fixed_asset_create_uop_rejects_life_months(self, user):
        with pytest.raises(ValidationException, match="Thời gian khấu hao không được cung cấp"):
            fixed_asset_create(
                user=user,
                asset_code="MOLD-UOP-2",
                asset_name="Khuôn UOP 2",
                original_value=Decimal("10000.00"),
                depreciation_method="unit_of_production",
                useful_life_months=12,
                designed_capacity=Decimal("10000.00"),
            )

    def test_fixed_asset_create_straight_line_requires_life_months(self, user):
        with pytest.raises(ValidationException, match="Số tháng khấu hao hữu ích phải lớn hơn 0"):
            fixed_asset_create(
                user=user,
                asset_code="MOLD-SL-1",
                asset_name="Khuôn SL 1",
                original_value=Decimal("10000.00"),
                depreciation_method="straight_line",
                useful_life_months=None,
            )

    def test_fixed_asset_create_straight_line_rejects_capacity(self, user):
        with pytest.raises(ValidationException, match="Công suất thiết kế không được cung cấp"):
            fixed_asset_create(
                user=user,
                asset_code="MOLD-SL-2",
                asset_name="Khuôn SL 2",
                original_value=Decimal("10000.00"),
                depreciation_method="straight_line",
                useful_life_months=12,
                designed_capacity=Decimal("10000.00"),
            )

    def test_fixed_asset_update_uop_blocks_life_months_change(self, user):
        asset = FixedAssetFactory(depreciation_method="unit_of_production", status="idle")
        with pytest.raises(ValidationException, match="Không thể sửa số tháng sử dụng hữu ích"):
            fixed_asset_update(
                user=user,
                asset_id=str(asset.id),
                useful_life_months=12,
            )

    def test_run_depreciation_straight_line_stops_at_zero_months(self, user):
        FixedAssetFactory(
            original_value=Decimal("10000.00"),
            salvage_value=Decimal("2000.00"),
            depreciation_method="straight_line",
            useful_life_months=10,
            remaining_life_months=0,
            accumulated_depreciation=Decimal("8000.00"),
        )
        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 0

    def test_run_depreciation_straight_line_still_writes_last_month(self, user):
        asset = FixedAssetFactory(
            original_value=Decimal("10000.00"),
            salvage_value=Decimal("2000.00"),
            depreciation_method="straight_line",
            useful_life_months=10,
            remaining_life_months=1,
            accumulated_depreciation=Decimal("7200.00"),
        )
        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 1
        assert logs[0].depreciation_amount == Decimal("800.00")

        asset.refresh_from_db()
        assert asset.accumulated_depreciation == Decimal("8000.00")
        assert asset.remaining_life_months == 0

    def test_run_depreciation_uop_stops_when_fully_depreciated(self, user):
        finished_good = ItemFactory()
        mold = FixedAssetFactory(
            original_value=Decimal("6000.00"),
            salvage_value=Decimal("1000.00"),
            depreciation_method="unit_of_production",
            useful_life_months=None,
            remaining_life_months=None,
            designed_capacity=Decimal("1000.00"),
            accumulated_depreciation=Decimal("5000.00"),
        )
        bom = BOMFactory(item=finished_good, is_active=True)
        from apps.inventory.tests.factories import WorkOrderFactory
        from apps.master_data.models import WorkOrderFixedAsset

        work_order = WorkOrderFactory(bom=bom, status="in_progress")
        WorkOrderFixedAsset.objects.create(work_order=work_order, fixed_asset=mold)

        warehouse = WarehouseFactory()
        posting_date = timezone.make_aware(datetime.datetime(2026, 6, 15, 12, 0, 0))
        entry = StockEntryFactory(
            purpose="manufacture", status="posted", posting_date=posting_date, work_order=work_order
        )
        StockEntryDetailFactory(
            parent=entry, item=finished_good, quantity=Decimal("150.00"), target_warehouse=warehouse
        )

        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 0

    def test_run_depreciation_uop_writes_when_qty_exceeds_capacity(self, user):
        finished_good = ItemFactory()
        mold = FixedAssetFactory(
            original_value=Decimal("6000.00"),
            salvage_value=Decimal("1000.00"),
            depreciation_method="unit_of_production",
            useful_life_months=None,
            remaining_life_months=None,
            designed_capacity=Decimal("1000.00"),
            accumulated_depreciation=Decimal("4500.00"),  # 500 VND remaining depreciable value
        )
        bom = BOMFactory(item=finished_good, is_active=True)
        from apps.inventory.tests.factories import WorkOrderFactory
        from apps.master_data.models import WorkOrderFixedAsset

        work_order = WorkOrderFactory(bom=bom, status="in_progress")
        WorkOrderFixedAsset.objects.create(work_order=work_order, fixed_asset=mold)

        warehouse = WarehouseFactory()
        posting_date = timezone.make_aware(datetime.datetime(2026, 6, 15, 12, 0, 0))
        entry = StockEntryFactory(
            purpose="manufacture", status="posted", posting_date=posting_date, work_order=work_order
        )
        StockEntryDetailFactory(
            parent=entry, item=finished_good, quantity=Decimal("200.00"), target_warehouse=warehouse
        )

        # 200 units * 5 VND/unit = 1000 VND, but cap at 500 VND
        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 1
        assert logs[0].depreciation_amount == Decimal("500.00")

        mold.refresh_from_db()
        assert mold.accumulated_depreciation == Decimal("5000.00")

    def test_run_depreciation_uop_cap_then_no_more_log(self, user):
        finished_good = ItemFactory()
        mold = FixedAssetFactory(
            original_value=Decimal("6000.00"),
            salvage_value=Decimal("1000.00"),
            depreciation_method="unit_of_production",
            useful_life_months=None,
            remaining_life_months=None,
            designed_capacity=Decimal("1000.00"),
            accumulated_depreciation=Decimal("5000.00"),  # fully depreciated
        )
        bom = BOMFactory(item=finished_good, is_active=True)
        from apps.inventory.tests.factories import WorkOrderFactory
        from apps.master_data.models import WorkOrderFixedAsset

        work_order = WorkOrderFactory(bom=bom, status="in_progress")
        WorkOrderFixedAsset.objects.create(work_order=work_order, fixed_asset=mold)

        warehouse = WarehouseFactory()
        posting_date = timezone.make_aware(datetime.datetime(2026, 6, 15, 12, 0, 0))
        entry = StockEntryFactory(
            purpose="manufacture", status="posted", posting_date=posting_date, work_order=work_order
        )
        StockEntryDetailFactory(
            parent=entry, item=finished_good, quantity=Decimal("150.00"), target_warehouse=warehouse
        )

        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 0

    def test_run_depreciation_uop_zero_qty_when_partially_depreciated(self, user):
        finished_good = ItemFactory()
        mold = FixedAssetFactory(
            original_value=Decimal("6000.00"),
            salvage_value=Decimal("1000.00"),
            depreciation_method="unit_of_production",
            useful_life_months=None,
            remaining_life_months=None,
            designed_capacity=Decimal("1000.00"),
            accumulated_depreciation=Decimal("2000.00"),
        )
        bom = BOMFactory(item=finished_good, is_active=True)
        from apps.inventory.tests.factories import WorkOrderFactory
        from apps.master_data.models import WorkOrderFixedAsset

        work_order = WorkOrderFactory(bom=bom, status="in_progress")
        WorkOrderFixedAsset.objects.create(work_order=work_order, fixed_asset=mold)

        # No production -> prod_qty is 0
        logs = run_fixed_asset_depreciation(user=user, period="2026-06")
        assert len(logs) == 1
        assert logs[0].depreciation_amount == Decimal("0.00")

        mold.refresh_from_db()
        assert mold.accumulated_depreciation == Decimal("2000.00")

    def test_reject_purchase_clears_fk_and_deletes_asset(self, user):
        """
        Verify: Reject CF mua TSCĐ → asset + PO/PI bị xóa, FK trên CF clear.
        Regression test cho bug use-after-delete.
        """
        from apps.finance.models import CashFlowTransaction
        from apps.finance.services import cash_flow_reject
        from apps.purchasing.models import PurchaseInvoice, PurchaseOrder
        from apps.purchasing.tests.factories import PurchaseInvoiceFactory, PurchaseOrderFactory

        # Setup: tạo PO, PI, Asset (status pending_receive), CF (status pending_approval)
        po = PurchaseOrderFactory(total_amount=Decimal("50000000.00"))
        pi = PurchaseInvoiceFactory(order=po, total_amount=Decimal("50000000.00"))
        asset = FixedAssetFactory(original_value=Decimal("50000000.00"), status="pending_receive")
        cf = CashFlowTransaction.objects.create(
            payment_type="pay",
            category="Mua tài sản cố định",
            amount=Decimal("50000000.00"),
            payment_date="2026-06-15",
            status="pending_approval",
            purchase_order=po,
            purchase_invoice=pi,
            fixed_asset=asset,
        )

        # Act
        cash_flow_reject(user=user, tx_id=str(cf.id), remarks="Từ chối mua")

        # Assert
        cf.refresh_from_db()
        assert cf.status == "rejected"
        assert cf.fixed_asset_id is None
        assert cf.purchase_order_id is None
        assert cf.purchase_invoice_id is None
        assert cf.fixed_asset is None  # Should not raise DoesNotExist

        with pytest.raises(FixedAsset.DoesNotExist):
            FixedAsset.objects.get(id=asset.id)
        with pytest.raises(PurchaseOrder.DoesNotExist):
            PurchaseOrder.objects.get(id=po.id)
        with pytest.raises(PurchaseInvoice.DoesNotExist):
            PurchaseInvoice.objects.get(id=pi.id)
