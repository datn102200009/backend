from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.inventory.tests.factories import BOMItemFactory, ItemFactory, StockLedgerFactory
from apps.master_data.models import Item
from apps.master_data.services import item_create, item_delete, item_update


@pytest.mark.django_db
class TestItemServices:
    def test_item_create_success(self):
        item = item_create(item_code="NEW-001", item_name="New Item", minimum_threshold=10.0)
        assert item.id is not None
        assert item.item_code == "NEW-001"
        assert Item.objects.filter(item_code="NEW-001").exists()

    def test_item_create_duplicate_code(self):
        ItemFactory(item_code="DUP-001")
        with pytest.raises(ValidationError) as exc:
            item_create(item_code="DUP-001", item_name="Duplicate", minimum_threshold=10.0)
        assert "item_code" in exc.value.message_dict

    def test_item_update_success(self):
        item = ItemFactory(item_code="UPD-001", item_name="Old Name")
        updated_item = item_update(item=item, data={"item_name": "New Name"})
        assert updated_item.item_name == "New Name"

        # Verify non-updatable fields are ignored
        updated_item = item_update(item=item, data={"item_code": "CHANGED-001"})
        assert updated_item.item_code == "UPD-001"

    def test_item_delete_happy_path(self):
        item = ItemFactory(item_code="DEL-001")
        item_delete(item=item)
        assert not Item.objects.filter(item_code="DEL-001").exists()

    def test_item_delete_protected_error_stock_ledger(self):
        item = ItemFactory(item_code="DEL-002")
        StockLedgerFactory(item=item)

        with pytest.raises(ValidationError) as exc:
            item_delete(item=item)
        assert "Không thể xóa vật tư này" in str(exc.value)
        assert "Stock Ledger" in str(exc.value)

    def test_item_delete_protected_error_bom_item(self):
        item = ItemFactory(item_code="DEL-003")
        BOMItemFactory(item=item)

        with pytest.raises(ValidationError) as exc:
            item_delete(item=item)
        assert "Không thể xóa vật tư này" in str(exc.value)
        assert "BOM Item" in str(exc.value)

    @patch("apps.master_data.models.Item.save")
    def test_item_create_race_condition(self, mock_save):
        mock_save.side_effect = IntegrityError("Unique constraint failed")
        with pytest.raises(IntegrityError):
            item_create(item_code="RACE-001", item_name="Race", minimum_threshold=10.0)
