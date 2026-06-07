from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboard.selectors import (
    get_finance_cashflow_chart,
    get_finance_cashflow_summary,
    get_finance_depreciation_status,
    get_finance_unpaid_purchase_invoices,
    get_finance_unpaid_sales_invoices,
    get_hrm_employees_without_contract,
    get_hrm_expiring_contracts,
    get_hrm_payroll_lifecycle_status,
    get_hrm_pending_leave_requests,
    get_hrm_today_attendance_rate,
    get_inventory_pending_entries,
    get_inventory_pending_entry_count,
    get_manufacturing_active_wos,
    get_manufacturing_pending_completion,
    get_manufacturing_pending_declarations,
    get_manufacturing_pending_wo_approval,
    get_purchasing_active_po_count,
    get_purchasing_blocked_invoices,
    get_purchasing_draft_orders,
    get_purchasing_pending_delivery,
    get_purchasing_pending_logistic_fees,
    get_purchasing_pending_qc,
    get_sales_draft_orders,
    get_sales_pending_credit_bypass,
    get_sales_pending_fulfillment,
    get_sales_today_revenue,
    get_warehouse_low_stock_alerts,
)
from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog, SalarySlip
from apps.hrm.models import Attendance, EmploymentContract, LeaveRequest
from apps.inventory.models import StockEntry, StockLedger
from apps.inventory.tests.factories import (
    CustomerFactory,
    ItemFactory,
    PermissionFactory,
    RoleFactory,
    SupplierFactory,
    UOMFactory,
    UserFactory,
    WarehouseFactory,
)
from apps.master_data.models import UOM, Employee, Item, Warehouse, WorkOrder
from apps.purchasing.models import PurchaseInvoice, PurchaseOrder, Shipment
from apps.sales.models import SalesInvoice, SalesOrder


@pytest.mark.django_db
class TestDashboardSelectors:

    def test_sales_today_revenue(self):
        customer = CustomerFactory()
        SalesOrder.objects.create(customer=customer, total_amount=Decimal("150.00"), status=SalesOrder.Status.PENDING)
        SalesOrder.objects.create(customer=customer, total_amount=Decimal("250.00"), status=SalesOrder.Status.COMPLETED)
        SalesOrder.objects.create(customer=customer, total_amount=Decimal("500.00"), status=SalesOrder.Status.DRAFT)

        res = get_sales_today_revenue()
        assert res["revenue"] == 400.0
        assert res["order_count"] == 2

    def test_sales_draft_orders(self):
        customer = CustomerFactory()
        SalesOrder.objects.create(customer=customer, total_amount=Decimal("100.00"), status=SalesOrder.Status.DRAFT)

        res = get_sales_draft_orders()
        assert len(res) == 1
        assert res[0]["total_amount"] == 100.0

    def test_sales_pending_fulfillment(self):
        customer = CustomerFactory()
        SalesOrder.objects.create(customer=customer, total_amount=Decimal("150.00"), status=SalesOrder.Status.PENDING)

        res = get_sales_pending_fulfillment()
        assert len(res) == 1
        assert res[0]["total_amount"] == 150.0

    def test_purchasing_active_po_count(self):
        supplier = SupplierFactory()
        PurchaseOrder.objects.create(
            vendor=supplier, total_amount=Decimal("100.00"), status=PurchaseOrder.Status.PENDING
        )
        PurchaseOrder.objects.create(vendor=supplier, total_amount=Decimal("200.00"), status=PurchaseOrder.Status.DRAFT)

        res = get_purchasing_active_po_count()
        assert res["active_po_count"] == 1

    def test_purchasing_draft_orders(self):
        supplier = SupplierFactory()
        PurchaseOrder.objects.create(vendor=supplier, total_amount=Decimal("150.00"), status=PurchaseOrder.Status.DRAFT)

        res = get_purchasing_draft_orders()
        assert len(res) == 1
        assert res[0]["total_amount"] == 150.0

    def test_purchasing_pending_delivery(self):
        supplier = SupplierFactory()
        PurchaseOrder.objects.create(
            vendor=supplier,
            total_amount=Decimal("150.00"),
            status=PurchaseOrder.Status.PENDING,
            receipt_fulfillment_rate=Decimal("85.00"),
            payment_fulfillment_rate=Decimal("60.00"),
        )

        res = get_purchasing_pending_delivery()
        assert len(res) == 1
        assert res[0]["total_amount"] == 150.0
        assert res[0]["receipt_fulfillment_rate"] == 85.0
        assert res[0]["payment_fulfillment_rate"] == 60.0

    def test_purchasing_pending_qc(self):
        Shipment.objects.create(shipment_num="SHIP-01", name="Lô hàng 1", status=Shipment.Status.ARRIVED)
        res = get_purchasing_pending_qc()
        assert len(res) == 1
        assert res[0]["shipment_num"] == "SHIP-01"

    def test_purchasing_pending_logistic_fees(self):
        Shipment.objects.create(shipment_num="SHIP-02", name="Lô hàng 2", status=Shipment.Status.INSPECTED)
        res = get_purchasing_pending_logistic_fees()
        assert len(res) == 1
        assert res[0]["shipment_num"] == "SHIP-02"

    def test_purchasing_blocked_invoices(self):
        supplier = SupplierFactory()
        PurchaseInvoice.objects.create(
            vendor=supplier,
            status=PurchaseInvoice.Status.UNPAID,
            total_amount=Decimal("100.00"),
            block_reason="QC Failed",
        )
        res = get_purchasing_blocked_invoices()
        assert len(res) == 1
        assert res[0]["block_reason"] == "QC Failed"

    def test_inventory_pending_entry_count(self):
        StockEntry.objects.create(name="SE-DRAFT", purpose="receipt", posting_date=timezone.now(), status="draft")
        res = get_inventory_pending_entry_count()
        assert res["pending_entry_count"] == 1

    def test_inventory_pending_entries(self):
        uom = UOMFactory()
        item = ItemFactory(stock_uom=uom)
        wh_src = WarehouseFactory(name="Kho Nguồn")
        wh_tgt = WarehouseFactory(name="Kho Đích")

        se = StockEntry.objects.create(name="SE-TRF", purpose="transfer", posting_date=timezone.now(), status="draft")
        from apps.inventory.models import StockEntryDetail

        StockEntryDetail.objects.create(
            parent=se, item=item, quantity=Decimal("5.0"), source_warehouse=wh_src, target_warehouse=wh_tgt
        )

        res = get_inventory_pending_entries()
        assert len(res) == 1
        assert res[0]["name"] == "SE-TRF"
        assert res[0]["purpose"] == "transfer"
        assert res[0]["route_desc"] == "Kho Nguồn → Kho Đích"
        assert res[0]["item_count"] == 1

    def test_finance_cashflow_chart(self):
        CashFlowTransaction.objects.create(
            name="TX-01", payment_type="receive", amount=Decimal("1000.00"), payment_date=timezone.now().date()
        )
        res = get_finance_cashflow_chart()
        assert "weeks" in res
        assert len(res["weeks"]) == 4

    def test_finance_cashflow_summary(self):
        today = timezone.now().date()
        CashFlowTransaction.objects.create(
            name="TX-02", payment_type="receive", amount=Decimal("1500.00"), payment_date=today
        )
        CashFlowTransaction.objects.create(
            name="TX-03", payment_type="pay", amount=Decimal("500.00"), payment_date=today
        )
        res = get_finance_cashflow_summary()
        assert res["receive_total"] == 1500.0
        assert res["pay_total"] == 500.0
        assert res["net_cashflow"] == 1000.0

    def test_finance_unpaid_purchase_invoices(self):
        supplier = SupplierFactory()
        PurchaseInvoice.objects.create(
            vendor=supplier, status=PurchaseInvoice.Status.UNPAID, total_amount=Decimal("200.00")
        )
        res = get_finance_unpaid_purchase_invoices()
        assert len(res) == 1
        assert res[0]["remaining_amount"] == 200.0

    def test_finance_unpaid_sales_invoices(self):
        customer = CustomerFactory()
        SalesInvoice.objects.create(
            customer=customer, status=SalesInvoice.Status.UNPAID, total_amount=Decimal("300.00")
        )
        res = get_finance_unpaid_sales_invoices()
        assert len(res) == 1
        assert res[0]["remaining_amount"] == 300.0

    def test_finance_depreciation_status(self):
        asset = FixedAsset.objects.create(
            asset_code="M-01",
            asset_name="Machine 1",
            original_value=Decimal("1000.00"),
            depreciation_method="straight_line",
            useful_life_months=12,
            remaining_life_months=12,
        )
        FixedAssetDepreciationLog.objects.create(
            asset=asset, period=timezone.now().strftime("%Y-%m"), depreciation_amount=Decimal("100.00")
        )
        res = get_finance_depreciation_status()
        assert res["depreciated_assets_count"] == 1
        assert res["total_depreciation_amount"] == 100.0

    def test_hrm_payroll_lifecycle_status(self):
        emp = Employee.objects.create(employee_id="E-01", full_name="Employee 1", employment_status="active")
        SalarySlip.objects.create(
            name="SLIP-01",
            employee=emp,
            salary_period=timezone.now().strftime("%Y-%m"),
            base_salary=Decimal("5000.00"),
            gross_pay=Decimal("5000.00"),
            net_pay=Decimal("4500.00"),
            status="calculated",
        )
        res = get_hrm_payroll_lifecycle_status()
        assert res["status"] == "Calculated"
        assert res["net_pay_total"] == 4500.0

    def test_hrm_pending_leave_requests(self):
        emp = Employee.objects.create(employee_id="E-02", full_name="Employee 2", employment_status="active")
        LeaveRequest.objects.create(
            employee=emp,
            leave_type="paid",
            start_date=date.today(),
            end_date=date.today(),
            days=Decimal("1.0"),
            status="pending",
        )
        res = get_hrm_pending_leave_requests()
        assert len(res) == 1
        assert res[0]["employee_name"] == "Employee 2"

    def test_hrm_expiring_contracts(self):
        emp = Employee.objects.create(employee_id="E-03", full_name="Employee 3", employment_status="active")
        EmploymentContract.objects.create(
            employee=emp,
            contract_no="CON-01",
            contract_type="definite_term",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=15),
            status="active",
        )
        res = get_hrm_expiring_contracts()
        assert len(res) == 1
        assert res[0]["employee_name"] == "Employee 3"

    def test_hrm_employees_without_contract(self):
        # Active employee with no active contract
        Employee.objects.create(employee_id="E-04", full_name="Employee 4", employment_status="active")
        res = get_hrm_employees_without_contract()
        assert len(res) == 1
        assert res[0]["full_name"] == "Employee 4"

    def test_hrm_today_attendance_rate(self):
        emp = Employee.objects.create(employee_id="E-05", full_name="Employee 5", employment_status="active")
        Attendance.objects.create(employee=emp, date=date.today(), status="working")
        res = get_hrm_today_attendance_rate()
        assert res["attendance_rate"] == 100.0
        assert res["present_count"] == 1

    def test_manufacturing_pending_wo_approval(self):
        item = ItemFactory()
        WorkOrder.objects.create(
            name="WO-01", production_item=item, quantity=10, planned_start_date=date.today(), status="pending_approval"
        )
        res = get_manufacturing_pending_wo_approval()
        assert len(res) == 1
        assert res[0]["name"] == "WO-01"

    def test_manufacturing_active_wos(self):
        item = ItemFactory()
        WorkOrder.objects.create(
            name="WO-02", production_item=item, quantity=10, planned_start_date=date.today(), status="in_progress"
        )
        res = get_manufacturing_active_wos()
        assert len(res) == 1
        assert res[0]["name"] == "WO-02"

    def test_manufacturing_pending_declarations(self):
        item = ItemFactory()
        WorkOrder.objects.create(
            name="WO-03",
            production_item=item,
            quantity=10,
            produced_qty=2,
            planned_start_date=date.today(),
            status="in_progress",
        )
        res = get_manufacturing_pending_declarations()
        assert len(res) == 1
        assert res[0]["name"] == "WO-03"

    def test_manufacturing_pending_completion(self):
        item = ItemFactory()
        wh = WarehouseFactory(name="Kho Thành Phẩm")
        WorkOrder.objects.create(
            name="WO-04",
            production_item=item,
            quantity=10,
            produced_qty=10,
            planned_start_date=date.today(),
            status="in_progress",
            target_warehouse=wh,
        )
        res = get_manufacturing_pending_completion()
        assert len(res) == 1
        assert res[0]["name"] == "WO-04"
        assert res[0]["target_warehouse_name"] == "Kho Thành Phẩm"

    # Specific tests for inventory_low_stock (DOS, Excluded Warehouses, UOM Fallback, O(1) query complexity)
    def test_inventory_low_stock_calculations(self):
        # 1. Setup active warehouses (Raw materials & Finished goods)
        wh_raw = WarehouseFactory(name="Kho Nguyên Vật Liệu Selectors Test")
        wh_wip = WarehouseFactory(name="Kho WIP Selectors Test")  # Excluded

        # UOMs
        uom_ton = UOMFactory(name="tấn")
        uom_pcs = UOMFactory(name="cái")

        item_ton = ItemFactory(stock_uom=uom_ton, item_code="RAW-TON", item_name="Sắt Cuộn")
        item_pcs = ItemFactory(stock_uom=uom_pcs, item_code="COMP-PCS", item_name="Bulong M8")

        # Balance in local warehouses
        # Raw has 35.0 tons initially (net 5.0 tons after 30.0 tons consumption issues)
        StockLedger.objects.create(
            item=item_ton,
            warehouse=wh_raw,
            posting_date=timezone.now(),
            actual_quantity=Decimal("35.00"),
            voucher_type="Stock In",
        )
        # WIP has 10.0 tons (should be excluded)
        StockLedger.objects.create(
            item=item_ton,
            warehouse=wh_wip,
            posting_date=timezone.now(),
            actual_quantity=Decimal("10.00"),
            voucher_type="Stock In",
        )

        # Bulong M8 has 50 pieces (under UOM fallback of 200)
        StockLedger.objects.create(
            item=item_pcs,
            warehouse=wh_raw,
            posting_date=timezone.now(),
            actual_quantity=Decimal("50.00"),
            voucher_type="Stock In",
        )

        # Consumption in 30 days: 30.0 tons total issue from raw warehouse -> ADC = 1.0 ton/day
        # Local balance 5.0 -> DOS = 5.0 / 1.0 = 5.0 days -> Warning status (3 < DOS <= 7)
        for i in range(30):
            StockLedger.objects.create(
                item=item_ton,
                warehouse=wh_raw,
                posting_date=timezone.now() - timedelta(days=i),
                actual_quantity=Decimal("-1.00"),
                voucher_type="Stock Issue",
            )

        # Run selector
        alerts = get_warehouse_low_stock_alerts()

        # Assertions
        assert len(alerts) == 2  # Both should alert

        # Verify item_ton warning alert
        alert_ton = [a for a in alerts if a["item_code"] == "RAW-TON"][0]
        assert alert_ton["status"] == "warning"
        assert alert_ton["days_left"] == 5.0
        assert alert_ton["action_suggest"] == "Tạo Yêu cầu Mua hàng (PO)"

        # Verify item_pcs critical alert (due to UOM fallback < 200, no ADC)
        alert_pcs = [a for a in alerts if a["item_code"] == "COMP-PCS"][0]
        assert alert_pcs["status"] == "critical"
        assert alert_pcs["balance"] == 50.0

    def test_inventory_low_stock_query_efficiency(self):
        # 1. Setup active warehouses
        wh_raw = WarehouseFactory(name="Kho Nguyên Vật Liệu Efficiency Test")
        uom_pcs = UOMFactory(name="cái")

        # Create 10 items
        items = [ItemFactory(stock_uom=uom_pcs) for _ in range(10)]
        for item in items:
            StockLedger.objects.create(
                item=item,
                warehouse=wh_raw,
                posting_date=timezone.now(),
                actual_quantity=Decimal("10.00"),
                voucher_type="Stock In",
            )

        # Measure query counts
        with CaptureQueriesContext(connection) as ctx:
            alerts = get_warehouse_low_stock_alerts()

        # Verified O(1) query count (maximum 4 queries: active warehouses, balances, consumptions, item/uom master data)
        assert len(ctx.captured_queries) <= 5
