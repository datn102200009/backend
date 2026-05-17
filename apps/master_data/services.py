"""
Services for master_data app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.
"""

from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError

from apps.master_data.models import UOM, Item, ItemGroup


@transaction.atomic
def item_create(*, item_code: str, item_name: str, **kwargs: Any) -> Item:
    """
    Create a new Item.
    Raises ValidationError if item_code already exists.
    """
    if Item.objects.filter(item_code=item_code).exists():
        raise ValidationError({"item_code": "Item with this code already exists."})

    # Convert UUID strings to model instances if needed, though Django handles UUID strings for FKs automatically.
    # However, it's safer to just pass kwargs if they match field names (e.g. item_group_id)
    item = Item(item_code=item_code, item_name=item_name, **kwargs)
    item.full_clean()
    item.save()

    return item


@transaction.atomic
def item_update(*, item: Item, data: Dict[str, Any]) -> Item:
    """
    Update an existing Item.
    """
    non_updatable_fields = ["id", "item_code", "created_at", "updated_at"]

    for field, value in data.items():
        if field not in non_updatable_fields:
            setattr(item, field, value)

    item.full_clean()
    item.save()

    return item


@transaction.atomic
def item_delete(*, item: Item) -> None:
    """
    Delete an Item.
    Checks for ProtectedError which triggers if the item is referenced by
    StockLedger, StockEntryDetail, BOM, BOMItem, WorkOrder, etc.
    """
    try:
        item.delete()
    except ProtectedError as e:
        # e.protected_objects contains the list of related objects preventing deletion
        related_models = set([obj._meta.verbose_name for obj in e.protected_objects])
        models_str = ", ".join(related_models)
        raise ValidationError(
            f"Không thể xóa vật tư này vì dữ liệu đã được sử dụng trong: {models_str}. "
            "Vui lòng vô hiệu hóa (Inactive) thay vì xóa."
        )
