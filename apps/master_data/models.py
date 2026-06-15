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


class Employee(BaseModel):
    """
    Employee information.
    """

    employee_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    department = models.CharField(max_length=255, null=True, blank=True)
    position_title = models.CharField(max_length=255, null=True, blank=True)
    salary_base = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    is_union_member = models.BooleanField(default=False)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        null=True,
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    emergency_contact = models.TextField(null=True, blank=True)
    join_date = models.DateField(null=True, blank=True)
    leave_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=20,
        choices=[("active", "Active"), ("inactive", "Inactive")],
        default="active",
    )

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
    minimum_threshold = models.DecimalField(
        max_digits=18,
        decimal_places=3,
        default=0.0,
        help_text="Ngưỡng tối thiểu tồn kho. Bắt buộc nhập.",
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
    Lệnh sản xuất liên kết với BOM và sản phẩm cần sản xuất.
    """

    name = models.CharField(max_length=255, unique=True)
    bom = models.ForeignKey(
        "BOM",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_orders",
    )
    production_item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="work_orders",
        db_column="production_item_id",
    )
    quantity = models.DecimalField(max_digits=15, decimal_places=2)
    produced_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    source_warehouse = models.ForeignKey(
        "Warehouse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wo_source",
    )
    target_warehouse = models.ForeignKey(
        "Warehouse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wo_target",
    )
    production_warehouse = models.ForeignKey(
        "Warehouse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wo_production",
    )
    status = models.CharField(
        max_length=32,
        choices=[
            ("pending_approval", "Pending Approval"),
            ("in_progress", "In Progress"),
            ("pending_production_complete", "Pending Production Complete"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending_approval",
    )
    planned_start_date = models.DateField()
    planned_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "work_order"
        verbose_name = "Work Order"
        verbose_name_plural = "Work Orders"

    def __str__(self):
        return self.name


class WorkOrderFixedAsset(BaseModel):
    """
    Bảng trung gian (N-N) giữa WorkOrder và FixedAsset.
    Một WorkOrder có thể dùng 0, 1 hoặc nhiều tài sản UOP.
    Một FixedAsset có thể được dùng cho nhiều WorkOrder.
    """

    work_order = models.ForeignKey(
        "WorkOrder",
        on_delete=models.CASCADE,
        related_name="fixed_asset_links",
    )
    fixed_asset = models.ForeignKey(
        "finance.FixedAsset",
        on_delete=models.PROTECT,
        related_name="work_order_links",
    )

    class Meta:
        db_table = "work_order_fixed_asset"
        verbose_name = "Work Order - Fixed Asset Link"
        verbose_name_plural = "Work Order - Fixed Asset Links"
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "fixed_asset"],
                name="unique_work_order_fixed_asset",
            ),
        ]
        indexes = [
            models.Index(fields=["work_order"]),
            models.Index(fields=["fixed_asset"]),
        ]

    def __str__(self):
        return f"WO:{self.work_order_id} ↔ FA:{self.fixed_asset_id}"


class BOM(BaseModel):
    """
    Bill of Materials (Định mức vật tư).
    Mô tả danh sách nguyên vật liệu cần để sản xuất một thành phẩm.
    Trạng thái được quản lý qua field `is_active` từ BaseModel.
    """

    name = models.CharField(max_length=255, unique=True)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="boms")
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=1,
        help_text="Số lượng thành phẩm tiêu chuẩn cho định mức này",
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "bom"
        verbose_name = "Bill of Materials"
        verbose_name_plural = "Bills of Materials"
        constraints = [
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(is_active=True),
                name="unique_active_bom_per_item",
            )
        ]

    def __str__(self):
        return self.name


class BOMItem(BaseModel):
    """
    Chi tiết linh kiện/nguyên liệu trong BOM.
    """

    parent = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = "bom_item"
        verbose_name = "BOM Item"
        verbose_name_plural = "BOM Items"
        unique_together = ("parent", "item")

    def __str__(self):
        return f"{self.parent.name} - {self.item.item_code}"
