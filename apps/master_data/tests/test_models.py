import pytest
from django.db import IntegrityError, transaction

from apps.inventory.tests.factories import BOMFactory, ItemFactory


@pytest.mark.django_db
def test_bom_unique_active_constraint():
    # Arrange
    item = ItemFactory()

    # 1. Create first active BOM for item
    BOMFactory(item=item, is_active=True, name="BOM-Active-1")

    # 2. Creating another active BOM for same item should fail
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BOMFactory(item=item, is_active=True, name="BOM-Active-2")

    # 3. Creating an inactive BOM for same item should succeed
    BOMFactory(item=item, is_active=False, name="BOM-Inactive")
