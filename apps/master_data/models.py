from django.db import models

from apps.common.models import BaseModel


class ItemGroup(BaseModel):
    """
    Item Group for categorizing items hierarchically.
    """

    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    is_group = models.BooleanField(default=True)

    class Meta:
        db_table = "item_group"
        verbose_name = "Item Group"
        verbose_name_plural = "Item Groups"

    def __str__(self):
        return self.name


class UOM(BaseModel):
    """
    Unit of Measurement for items.
    """

    name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "uom"
        verbose_name = "Unit of Measurement"
        verbose_name_plural = "Units of Measurement"

    def __str__(self):
        return self.name


class Warehouse(BaseModel):
    """
    Warehouse for inventory storage.
    """

    name = models.CharField(max_length=255, unique=True)
    is_group = models.BooleanField(default=False)
    company = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "warehouse"
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"

    def __str__(self):
        return self.name


class Supplier(BaseModel):
    """
    Supplier information.
    """

    name = models.CharField(max_length=255, unique=True)
    supplier_name = models.CharField(max_length=255)
    supplier_group = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "supplier"
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def __str__(self):
        return self.name


class Customer(BaseModel):
    """
    Customer information.
    """

    name = models.CharField(max_length=255, unique=True)
    customer_name = models.CharField(max_length=255)
    customer_group = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "customer"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return self.name


class Employee(BaseModel):
    """
    Employee information.
    """

    employee_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    department = models.CharField(max_length=255, null=True, blank=True)
    salary_base = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    is_union_member = models.BooleanField(default=False)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "employee"
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"


class Item(BaseModel):
    """
    Item/Product information.
    """

    item_code = models.CharField(max_length=100, unique=True)
    item_name = models.CharField(max_length=255)
    item_group = models.ForeignKey(ItemGroup, on_delete=models.SET_NULL, null=True, blank=True)
    stock_uom = models.ForeignKey(UOM, on_delete=models.SET_NULL, null=True, blank=True)
    hs_code = models.CharField(max_length=20, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    recycling_coef_a = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    vat_group = models.CharField(max_length=50, null=True, blank=True)
    is_import = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("discontinued", "Discontinued"),
        ],
        default="active",
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "item"
        verbose_name = "Item"
        verbose_name_plural = "Items"

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"


class ModeOfPayment(BaseModel):
    """
    Payment method/mode.
    """

    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(
        max_length=50,
        choices=[
            ("cash", "Cash"),
            ("bank_transfer", "Bank Transfer"),
            ("check", "Check"),
            ("credit_card", "Credit Card"),
            ("other", "Other"),
        ],
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "mode_of_payment"
        verbose_name = "Mode of Payment"
        verbose_name_plural = "Modes of Payment"

    def __str__(self):
        return self.name


class WorkOrder(BaseModel):
    """
    Work Order / Manufacturing Order.
    """

    name = models.CharField(max_length=255, unique=True)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("released", "Released"),
            ("started", "Started"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )
    planned_start_date = models.DateTimeField()
    planned_end_date = models.DateTimeField()
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "work_order"
        verbose_name = "Work Order"
        verbose_name_plural = "Work Orders"

    def __str__(self):
        return self.name


class BOM(BaseModel):
    """
    Bill of Materials (Định mức vật tư).
    """

    name = models.CharField(max_length=255, unique=True)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        default="draft",
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "bom"
        verbose_name = "Bill of Materials"
        verbose_name_plural = "Bills of Materials"

    def __str__(self):
        return self.name


class BOMItem(BaseModel):
    """
    Item detail in BOM.
    """

    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=15, decimal_places=2)
    uom = models.ForeignKey(UOM, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "bom_item"
        verbose_name = "BOM Item"
        verbose_name_plural = "BOM Items"
        unique_together = ("bom", "item")

    def __str__(self):
        return f"{self.bom.name} - {self.item.item_code}"
