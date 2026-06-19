import pytest

from apps.master_data.api.v1.serializers import ItemCreateInputSerializer, ItemUpdateInputSerializer


class TestItemCreateInputSerializer:
    def test_valid_data(self):
        data = {
            "item_code": "ITEM-001",
            "item_name": "Test Item",
            "recycling_coef_a": "0.1",
            "status": "active",
            "minimum_threshold": "10.0",
        }
        serializer = ItemCreateInputSerializer(data=data)
        assert serializer.is_valid()

    def test_missing_minimum_threshold(self):
        data = {
            "item_code": "ITEM-001",
            "item_name": "Test Item",
            "recycling_coef_a": "0.1",
            "status": "active",
        }
        serializer = ItemCreateInputSerializer(data=data)
        assert not serializer.is_valid()
        assert "minimum_threshold" in serializer.errors

    def test_invalid_recycling_coef_negative(self):
        data = {
            "item_code": "ITEM-001",
            "item_name": "Test Item",
            "recycling_coef_a": "-0.1",
            "minimum_threshold": "10.0",
        }
        serializer = ItemCreateInputSerializer(data=data)
        assert not serializer.is_valid()
        assert "recycling_coef_a" in serializer.errors


class TestItemUpdateInputSerializer:
    def test_valid_update(self):
        data = {
            "item_name": "Updated Item",
            "minimum_threshold": "5.0",
        }
        serializer = ItemUpdateInputSerializer(data=data)
        assert serializer.is_valid()

    def test_update_missing_minimum_threshold(self):
        data = {
            "item_name": "Updated Item",
        }
        serializer = ItemUpdateInputSerializer(data=data)
        assert not serializer.is_valid()
        assert "minimum_threshold" in serializer.errors
