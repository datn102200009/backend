import pytest
from django.db import IntegrityError, transaction

from apps.inventory.tests.factories import StockEntryDetailFactory


@pytest.mark.django_db
def test_stock_entry_detail_quantity_check_constraint():
    # Arrange & Act & Assert
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            # Quantity = 0 should trigger CheckConstraint
            StockEntryDetailFactory(quantity=0)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            # Negative quantity should trigger CheckConstraint
            StockEntryDetailFactory(quantity=-5)
