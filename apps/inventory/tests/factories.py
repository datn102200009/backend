"""
Factories for creating test data.

Sử dụng factory_boy để tạo dữ liệu test.
"""

from datetime import datetime
from decimal import Decimal

import factory

from apps.accounts.models import Permission, Role, RolePermission, User
from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger
from apps.master_data.models import BOM, UOM, BOMItem, Item, ItemGroup, Warehouse, WorkOrder


class RoleFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Role."""

    class Meta:
        model = Role

    name = factory.Sequence(lambda n: f"Role-{n}")
    description = factory.Faker("text")


class PermissionFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Permission."""

    class Meta:
        model = Permission

    code = factory.Sequence(lambda n: f"permission.code_{n}")
    name = factory.Faker("word")


class UserFactory(factory.django.DjangoModelFactory):
    """Factory để tạo User."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password_hash = "hashed_password_123"
    role = factory.SubFactory(RoleFactory)
    employee_id = factory.Sequence(lambda n: f"EMP{n:04d}")


class ItemGroupFactory(factory.django.DjangoModelFactory):
    """Factory để tạo ItemGroup."""

    class Meta:
        model = ItemGroup

    name = factory.Sequence(lambda n: f"Item Group {n}")
    is_group = True


class UOMFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Unit of Measurement."""

    class Meta:
        model = UOM

    name = factory.Sequence(lambda n: f"UOM-{n}")


class WarehouseFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Warehouse."""

    class Meta:
        model = Warehouse

    name = factory.Sequence(lambda n: f"Warehouse-{n}")
    is_group = False
    company = "Company A"


class ItemFactory(factory.django.DjangoModelFactory):
    """Factory để tạo Item."""

    class Meta:
        model = Item

    item_code = factory.Sequence(lambda n: f"ITEM-{n:04d}")
    item_name = factory.Faker("word")
    item_group = factory.SubFactory(ItemGroupFactory)
    stock_uom = factory.SubFactory(UOMFactory)
    status = "active"
    is_import = False
    weight_kg = Decimal("1.00")
    recycling_coef_a = Decimal("0.05")


class BOMFactory(factory.django.DjangoModelFactory):
    """Factory để tạo BOM."""

    class Meta:
        model = BOM

    name = factory.Sequence(lambda n: f"BOM-{n:04d}")
    item = factory.SubFactory(ItemFactory)
    status = "active"
    description = factory.Faker("text")


class BOMItemFactory(factory.django.DjangoModelFactory):
    """Factory để tạo BOMItem."""

    class Meta:
        model = BOMItem

    bom = factory.SubFactory(BOMFactory)
    item = factory.SubFactory(ItemFactory)
    qty = Decimal("10.00")
    uom = factory.SubFactory(UOMFactory)


class WorkOrderFactory(factory.django.DjangoModelFactory):
    """Factory để tạo WorkOrder."""

    class Meta:
        model = WorkOrder

    name = factory.Sequence(lambda n: f"WO-{n:04d}")
    item = factory.SubFactory(ItemFactory)
    qty = Decimal("100.00")
    status = "released"
    planned_start_date = factory.Faker("date_time")
    planned_end_date = factory.Faker("date_time")


class StockEntryFactory(factory.django.DjangoModelFactory):
    """Factory để tạo StockEntry."""

    class Meta:
        model = StockEntry

    name = factory.Sequence(lambda n: f"SE-{n:04d}")
    purpose = "receipt"
    posting_date = factory.Faker("date_time")
    status = "draft"
    remarks = factory.Faker("text")


class StockEntryDetailFactory(factory.django.DjangoModelFactory):
    """Factory để tạo StockEntryDetail."""

    class Meta:
        model = StockEntryDetail

    parent = factory.SubFactory(StockEntryFactory)
    item = factory.SubFactory(ItemFactory)
    quantity = Decimal("50.00")
    source_warehouse = factory.SubFactory(WarehouseFactory)
    target_warehouse = factory.SubFactory(WarehouseFactory)


class StockLedgerFactory(factory.django.DjangoModelFactory):
    """Factory để tạo StockLedger."""

    class Meta:
        model = StockLedger

    item = factory.SubFactory(ItemFactory)
    warehouse = factory.SubFactory(WarehouseFactory)
    posting_date = factory.Faker("date_time")
    actual_quantity = Decimal("100.00")
    voucher_number = factory.Sequence(lambda n: f"VN-{n:04d}")
    voucher_type = "Stock In"
