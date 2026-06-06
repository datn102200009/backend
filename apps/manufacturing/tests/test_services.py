from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.inventory.models import StockEntry, StockLedger
from apps.inventory.tests.factories import (
    BOMFactory,
    BOMItemFactory,
    ItemFactory,
    StockLedgerFactory,
    WarehouseFactory,
    WorkOrderFactory,
)
from apps.manufacturing.services import (
    bom_create,
    bom_delete,
    bom_update,
    work_order_approve,
    work_order_complete,
    work_order_create,
    work_order_declare_production,
)
from apps.master_data.models import BOM, BOMItem, WorkOrder


@pytest.mark.django_db
class TestBOMServices:
    def test_bom_create_success(self, production_user):
        # Arrange
        finished_item = ItemFactory()
        component_item_1 = ItemFactory()
        component_item_2 = ItemFactory()

        items_data = [
            {"item_id": str(component_item_1.id), "quantity": Decimal("2.0")},
            {"item_id": str(component_item_2.id), "quantity": Decimal("3.0")},
        ]

        # Act
        bom = bom_create(
            user=production_user,
            name="New BOM",
            item_id=str(finished_item.id),
            quantity=Decimal("1.0"),
            description="Test description",
            items=items_data,
        )

        # Assert
        assert bom is not None
        assert bom.name == "New BOM"
        assert bom.item == finished_item
        assert bom.is_active is True
        assert bom.items.count() == 2

    def test_bom_create_missing_items(self, production_user):
        finished_item = ItemFactory()
        with pytest.raises(ValidationException, match="Định mức phải có ít nhất một linh kiện"):
            bom_create(
                user=production_user,
                name="New BOM",
                item_id=str(finished_item.id),
                items=[],
            )

    def test_bom_create_duplicate_name(self, production_user):
        bom = BOMFactory(name="Duplicate BOM")
        finished_item = ItemFactory()
        component_item = ItemFactory()

        with pytest.raises(ValidationException, match="Định mức 'Duplicate BOM' đã tồn tại"):
            bom_create(
                user=production_user,
                name="Duplicate BOM",
                item_id=str(finished_item.id),
                items=[{"item_id": str(component_item.id), "quantity": Decimal("1.0")}],
            )

    def test_bom_create_already_active(self, production_user):
        finished_item = ItemFactory()
        BOMFactory(item=finished_item, is_active=True, name="Old BOM")
        component_item = ItemFactory()

        with pytest.raises(ValidationException, match="đã có định mức đang hoạt động"):
            bom_create(
                user=production_user,
                name="New BOM",
                item_id=str(finished_item.id),
                items=[{"item_id": str(component_item.id), "quantity": Decimal("1.0")}],
            )

    def test_bom_create_component_is_finished_item(self, production_user):
        finished_item = ItemFactory()

        with pytest.raises(
            ValidationException,
            match="Linh kiện không được trùng với sản phẩm thành phẩm",
        ):
            bom_create(
                user=production_user,
                name="New BOM",
                item_id=str(finished_item.id),
                items=[{"item_id": str(finished_item.id), "quantity": Decimal("1.0")}],
            )

    def test_bom_update_success(self, production_user):
        bom = BOMFactory()
        BOMItemFactory(parent=bom)
        new_component = ItemFactory()

        updated_bom = bom_update(
            user=production_user,
            bom_id=str(bom.id),
            quantity=Decimal("5.0"),
            description="Updated description",
            items=[{"item_id": str(new_component.id), "quantity": Decimal("10.0")}],
        )

        assert updated_bom.quantity == Decimal("5.0")
        assert updated_bom.description == "Updated description"
        assert updated_bom.items.count() == 1
        assert updated_bom.items.first().item == new_component

    def test_bom_update_name_success(self, production_user):
        bom = BOMFactory(name="Old Name")
        BOMItemFactory(parent=bom)

        updated_bom = bom_update(
            user=production_user,
            bom_id=str(bom.id),
            name="New Updated Name",
        )

        assert updated_bom.name == "New Updated Name"

    def test_bom_update_name_duplicate(self, production_user):
        BOMFactory(name="Existing Name")
        bom = BOMFactory(name="Old Name")
        BOMItemFactory(parent=bom)

        with pytest.raises(ValidationException, match="Định mức 'Existing Name' đã tồn tại"):
            bom_update(
                user=production_user,
                bom_id=str(bom.id),
                name="Existing Name",
            )

    def test_bom_update_partial(self, production_user):
        bom = BOMFactory(quantity=Decimal("1.0"))
        BOMItemFactory(parent=bom)

        updated_bom = bom_update(
            user=production_user,
            bom_id=str(bom.id),
            quantity=Decimal("2.0"),
        )

        assert updated_bom.quantity == Decimal("2.0")
        # Ensure items were not updated/deleted when items=None
        assert updated_bom.items.count() == 1

    def test_bom_delete_success(self, production_user):
        bom = BOMFactory()
        BOMItemFactory(parent=bom)
        bom_id = str(bom.id)

        bom_delete(user=production_user, bom_id=bom_id)

        assert BOM.objects.filter(id=bom_id).exists() is False
        assert BOMItem.objects.filter(parent_id=bom_id).exists() is False

    def test_bom_delete_used_in_work_order(self, production_user):
        bom = BOMFactory()
        WorkOrderFactory(bom=bom)

        with pytest.raises(ValidationException, match="đang được sử dụng trong 1 lệnh sản xuất"):
            bom_delete(user=production_user, bom_id=str(bom.id))


@pytest.mark.django_db
class TestWorkOrderServices:
    def test_work_order_create_success(self, production_user):
        bom = BOMFactory(is_active=True)
        start_date = timezone.now().date()
        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        wo = work_order_create(
            user=production_user,
            name="New WO",
            bom_id=str(bom.id),
            quantity=100,
            source_warehouse_id=str(source.id),
            target_warehouse_id=str(target.id),
            production_warehouse_id=str(production.id),
            planned_start_date=start_date,
            remarks="Test remarks",
        )

        assert wo is not None
        assert wo.name == "New WO"
        assert wo.bom == bom
        assert wo.quantity == 100
        assert wo.status == "pending_approval"
        assert wo.planned_start_date == start_date
        assert wo.source_warehouse == source
        assert wo.target_warehouse == target
        assert wo.production_warehouse == production

    def test_work_order_create_inactive_bom(self, production_user):
        bom = BOMFactory(is_active=False)
        start_date = timezone.now().date()
        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        with pytest.raises(ValidationException, match="không hoạt động"):
            work_order_create(
                user=production_user,
                name="New WO",
                bom_id=str(bom.id),
                quantity=100,
                source_warehouse_id=str(source.id),
                target_warehouse_id=str(target.id),
                production_warehouse_id=str(production.id),
                planned_start_date=start_date,
            )

    def test_work_order_approve_success(self, production_user):
        bom = BOMFactory(is_active=True, quantity=Decimal("2.0"))
        item1 = ItemFactory()
        BOMItemFactory(parent=bom, item=item1, quantity=Decimal("2.0"))

        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        # Setup tồn kho nguyên liệu trong kho source
        StockLedgerFactory(
            item=item1,
            warehouse=source,
            actual_quantity=Decimal("50.00"),
            posting_date=timezone.now(),
            voucher_number="SETUP-STOCK",
            voucher_type="Stock In",
        )

        wo = WorkOrderFactory(
            bom=bom,
            quantity=10,
            status="pending_approval",
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
        )

        approved_wo = work_order_approve(user=production_user, work_order_id=str(wo.id))

        assert approved_wo.status == "in_progress"
        assert approved_wo.planned_start_date == timezone.now().date()

        # Verify TRF stock entry created
        trf_se = StockEntry.objects.filter(purpose="transfer", name__contains="RAW").first()
        assert trf_se is not None
        assert trf_se.details.count() == 1
        assert trf_se.details.first().quantity == Decimal("10.0")  # 2.0 * (10 / 2.0)
        assert trf_se.details.first().source_warehouse == source
        assert trf_se.details.first().target_warehouse == production

    def test_work_order_approve_invalid_status(self, production_user):
        wo = WorkOrderFactory(status="in_progress")
        with pytest.raises(
            ValidationException,
            match="Chỉ có thể phê duyệt lệnh ở trạng thái 'Chờ phê duyệt'",
        ):
            work_order_approve(user=production_user, work_order_id=str(wo.id))

    def test_work_order_declare_production_success(self, production_user):
        bom = BOMFactory(is_active=True, quantity=Decimal("2.0"))
        item1 = ItemFactory()
        BOMItemFactory(parent=bom, item=item1, quantity=Decimal("2.0"))

        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        wo = WorkOrderFactory(
            bom=bom,
            production_item=bom.item,
            quantity=10,
            status="in_progress",
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
        )

        declared_wo = work_order_declare_production(
            user=production_user, work_order_id=str(wo.id), produced_qty=Decimal("5.0")
        )

        assert declared_wo.status == "in_progress"

        # Verify MFG stock entry
        mfg_se = StockEntry.objects.filter(purpose="manufacture").first()
        assert mfg_se is not None

        # Should consume materials and produce item in production warehouse
        details = mfg_se.details.all()
        assert details.count() == 2

        consumption = details.get(item=item1)
        assert consumption.quantity == Decimal("5.0")  # 2.0 * (5.0 / 2.0)
        assert consumption.source_warehouse == production

        receipt = details.get(item=bom.item)
        assert receipt.quantity == Decimal("5.0")
        assert receipt.target_warehouse == production

    def test_work_order_complete_success(self, production_user):
        bom = BOMFactory(is_active=True)
        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        wo = WorkOrderFactory(
            bom=bom,
            production_item=bom.item,
            status="in_progress",
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
            quantity=100,
            produced_qty=100,
        )

        # Create a manufacture StockEntry to mock produced items
        se = StockEntry.objects.create(
            name=f"MFG-{wo.name}-123",
            purpose="manufacture",
            posting_date=timezone.now(),
            status="posted",
            work_order=wo,
            remarks=f"Nhập liệu sản xuất cho lệnh {wo.name}",
        )
        from apps.inventory.models import StockEntryDetail

        StockEntryDetail.objects.create(
            parent=se,
            item=wo.production_item,
            quantity=Decimal("100.0"),
            target_warehouse=production,
        )

        completed_wo = work_order_complete(
            user=production_user,
            work_order_id=str(wo.id),
        )

        assert completed_wo.status == "completed"
        assert completed_wo.actual_end_date == timezone.now().date()
        assert completed_wo.planned_end_date == timezone.now().date()

        # Verify TRF StockEntry created for finished goods
        trf_se = StockEntry.objects.filter(purpose="transfer", name__contains="FIN").first()
        assert trf_se is not None
        assert trf_se.details.count() == 1
        assert trf_se.details.first().quantity == Decimal("100.0")
        assert trf_se.details.first().target_warehouse == target

        # Verify StockLedger created for transfer
        sl = StockLedger.objects.filter(item=bom.item, warehouse=target).first()
        assert sl is not None
        assert sl.actual_quantity == Decimal("100.0")
        assert sl.voucher_type == "Transfer Receipt"

    def test_work_order_complete_invalid_status(self, production_user):
        wo = WorkOrderFactory(status="completed")

        with pytest.raises(ValidationException, match="Chỉ có thể hoàn thành lệnh đang thực hiện"):
            work_order_complete(
                user=production_user,
                work_order_id=str(wo.id),
            )

    def test_work_order_complete_substring_collision(self, production_user):
        """Test complete lệnh sản xuất không bị nhận nhầm stock entry của lệnh khác có tên chứa substring tương tự."""
        bom = BOMFactory(is_active=True)
        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        # Tạo lệnh sản xuất ngắn (WO-001) và lệnh sản xuất dài (WO-0010)
        wo_short = WorkOrderFactory(
            name="WO-001",
            bom=bom,
            production_item=bom.item,
            status="in_progress",
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
            quantity=100,
            produced_qty=100,
        )
        wo_long = WorkOrderFactory(
            name="WO-0010",
            bom=bom,
            production_item=bom.item,
            status="in_progress",
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
            quantity=100,
            produced_qty=100,
        )

        # Tạo phiếu sản xuất (manufacture StockEntry) cho lệnh WO-0010
        # Ghi remarks chứa tên lệnh "WO-0010" (có chứa substring "WO-001")
        # Gán khóa ngoại work_order = wo_long
        se_long = StockEntry.objects.create(
            name=f"MFG-{wo_long.name}-123",
            purpose="manufacture",
            posting_date=timezone.now(),
            status="posted",
            work_order=wo_long,
            remarks=f"Nhập liệu sản xuất cho lệnh {wo_long.name}",  # remarks contain 'WO-0010'
        )
        from apps.inventory.models import StockEntryDetail

        StockEntryDetail.objects.create(
            parent=se_long,
            item=wo_long.production_item,
            quantity=Decimal("100.0"),
            target_warehouse=production,
        )

        # Hoàn thành lệnh WO-001 (lệnh ngắn)
        completed_wo = work_order_complete(
            user=production_user,
            work_order_id=str(wo_short.id),
        )

        assert completed_wo.status == "completed"

        # Vì phiếu kho se_long thuộc về wo_long (qua FK), wo_short không được tính số lượng sản xuất từ se_long
        # Do đó, không có phiếu TRF thành phẩm nào của wo_short được tạo ra.
        trf_se = StockEntry.objects.filter(purpose="transfer", work_order=wo_short).first()
        assert trf_se is None

    def test_work_order_approve_with_nullable_fields(self, production_user):
        """Test work_order_approve runs successfully without select_related on nullable fields."""
        bom = BOMFactory(is_active=True, quantity=Decimal("1.0"))
        item1 = ItemFactory()
        BOMItemFactory(parent=bom, item=item1, quantity=Decimal("1.0"))

        source = WarehouseFactory()
        target = WarehouseFactory()
        production = WarehouseFactory()

        # Setup tồn kho nguyên liệu trong kho source
        StockLedgerFactory(
            item=item1,
            warehouse=source,
            actual_quantity=Decimal("10.00"),
            posting_date=timezone.now(),
            voucher_number="SETUP-STOCK",
            voucher_type="Stock In",
        )

        wo = WorkOrderFactory(
            bom=bom,
            quantity=5,
            status="pending_approval",
            source_warehouse=source,
            target_warehouse=target,
            production_warehouse=production,
        )

        # Act
        approved_wo = work_order_approve(user=production_user, work_order_id=str(wo.id))

        # Assert
        assert approved_wo.status == "in_progress"
        assert approved_wo.planned_start_date == timezone.now().date()
