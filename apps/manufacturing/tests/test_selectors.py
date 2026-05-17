import pytest

from apps.inventory.models import StockLedger
from apps.inventory.tests.factories import BOMFactory, BOMItemFactory, ItemFactory, WarehouseFactory, WorkOrderFactory
from apps.manufacturing.selectors import bom_detail, bom_list, get_material_preview, work_order_detail, work_order_list


@pytest.mark.django_db
class TestBOMSelectors:
    def test_bom_list(self, django_assert_num_queries):
        # Create some BOMs
        b1 = BOMFactory(is_active=True, name="BOM-Active")
        BOMItemFactory(parent=b1)
        b2 = BOMFactory(is_active=False, name="BOM-Inactive")
        BOMItemFactory(parent=b2)

        # Test filter is_active
        qs = bom_list(is_active=True)
        assert qs.count() == 1
        assert qs.first() == b1

        # Test search
        qs_search = bom_list(search="Inactive")
        assert qs_search.count() == 1
        assert qs_search.first() == b2

        # Test N+1 queries (should be 3: BOMs, BOMItems, Items)
        with django_assert_num_queries(3):
            boms = list(bom_list())
            for bom in boms:
                _ = bom.item.item_code
                _ = list(bom.items.all())

    def test_bom_detail(self):
        bom = BOMFactory()
        BOMItemFactory(parent=bom)

        result = bom_detail(bom_id=str(bom.id))

        assert result is not None
        assert result.id == bom.id
        assert result.items.count() == 1


@pytest.mark.django_db
class TestWorkOrderSelectors:
    def test_work_order_list(self, django_assert_num_queries):
        bom = BOMFactory()
        w1 = WorkOrderFactory(status="draft", name="WO-Draft", bom=bom)
        w2 = WorkOrderFactory(status="released", name="WO-Released", bom=bom)

        # Test status filter
        qs = work_order_list(status="draft")
        assert qs.count() == 1
        assert qs.first() == w1

        # Test search
        qs_search = work_order_list(search="Released")
        assert qs_search.count() == 1
        assert qs_search.first() == w2

        # Test N+1
        with django_assert_num_queries(1):
            wos = list(work_order_list())
            for wo in wos:
                _ = wo.bom.name
                _ = wo.production_item.item_code

    def test_work_order_detail(self):
        bom = BOMFactory()
        wo = WorkOrderFactory(bom=bom)

        result = work_order_detail(work_order_id=str(wo.id))

        assert result is not None
        assert result.id == wo.id
        assert result.bom is not None
        assert result.production_item is not None

    def test_get_material_preview_sufficient(self):
        from decimal import Decimal

        from django.utils import timezone

        bom = BOMFactory(quantity=Decimal("5.0"))
        item1 = ItemFactory()
        item2 = ItemFactory()
        BOMItemFactory(parent=bom, item=item1, quantity=Decimal("2.0"))
        BOMItemFactory(parent=bom, item=item2, quantity=Decimal("3.0"))

        warehouse = WarehouseFactory()

        # Add stock ledger for sufficient balance
        StockLedger.objects.create(
            item=item1,
            warehouse=warehouse,
            actual_quantity=Decimal("100.0"),
            posting_date=timezone.now(),
            voucher_type="test",
        )
        StockLedger.objects.create(
            item=item2,
            warehouse=warehouse,
            actual_quantity=Decimal("100.0"),
            posting_date=timezone.now(),
            voucher_type="test",
        )

        preview = get_material_preview(
            bom_id=str(bom.id),
            quantity=Decimal("10.0"),
            source_warehouse_id=str(warehouse.id),
        )

        assert len(preview) == 2
        # item1 needs 2.0 * (10.0 / 5.0) = 4.0, has 100
        p1 = next(p for p in preview if p["item_id"] == str(item1.id))
        assert p1["required_qty"] == 4.0
        assert p1["available_qty"] == 100.0
        assert p1["missing_qty"] == 0.0

    def test_get_material_preview_deficit(self):
        from decimal import Decimal

        from django.utils import timezone

        bom = BOMFactory(quantity=Decimal("2.0"))
        item1 = ItemFactory()
        BOMItemFactory(parent=bom, item=item1, quantity=Decimal("2.0"))

        warehouse = WarehouseFactory()

        # Add stock ledger for INSUFFICIENT balance
        StockLedger.objects.create(
            item=item1,
            warehouse=warehouse,
            actual_quantity=Decimal("5.0"),
            posting_date=timezone.now(),
            voucher_type="test",
        )

        preview = get_material_preview(
            bom_id=str(bom.id),
            quantity=Decimal("10.0"),
            source_warehouse_id=str(warehouse.id),
        )

        assert len(preview) == 1
        # item1 needs 2.0 * (10.0 / 2.0) = 10.0, has 5, missing 5
        p1 = preview[0]
        assert p1["required_qty"] == 10.0
        assert p1["available_qty"] == 5.0
        assert p1["missing_qty"] == 5.0
