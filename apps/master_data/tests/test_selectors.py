import pytest

from apps.inventory.tests.factories import ItemFactory
from apps.master_data.models import Item
from apps.master_data.selectors import item_get_detail, item_list


@pytest.mark.django_db
class TestItemSelectors:
    def test_item_list_optimization(self, django_assert_num_queries):
        ItemFactory.create_batch(5)
        # item_list has select_related("item_group", "stock_uom")
        qs = item_list()

        with django_assert_num_queries(1):
            items = list(qs)
            for item in items:
                # accessing related fields shouldn't trigger new queries
                _ = item.item_group
                _ = item.stock_uom

    def test_item_list_search_filter(self):
        ItemFactory(item_code="SEARCH-001", item_name="Apple")
        ItemFactory(item_code="OTHER-002", item_name="Banana")

        qs = item_list(search="Apple")
        assert qs.count() == 1
        assert qs.first().item_code == "SEARCH-001"

        qs_code = item_list(search="OTHER-002")
        assert qs_code.count() == 1

    def test_item_list_status_filter(self):
        ItemFactory(item_code="STAT-001", status="active")
        ItemFactory(item_code="STAT-002", status="inactive")

        qs = item_list(status="active")
        assert all(i.status == "active" for i in qs)

    def test_item_get_detail(self):
        item = ItemFactory(item_code="DET-001")
        found_item = item_get_detail(item_code="DET-001")
        assert found_item.id == item.id

        with pytest.raises(Item.DoesNotExist):
            item_get_detail(item_code="NON-EXISTENT")
