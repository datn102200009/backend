from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboard.selectors import (
    format_num,
    get_finance_cashflow_overview,
    get_finance_depreciation_status,
    get_finance_unpaid_purchase_invoices,
    get_finance_unpaid_sales_invoices,
    get_hrm_expiring_contracts,
    get_hrm_payroll_lifecycle_status,
    get_hrm_pending_leave_requests,
    get_hrm_today_attendance_rate,
    get_inventory_pending_entries,
    get_manufacturing_active_wos,
    get_manufacturing_pending_completion,
    get_manufacturing_pending_declarations,
    get_manufacturing_pending_wo_approval,
    get_purchasing_active_po_count,
    get_purchasing_draft_orders,
    get_purchasing_pending_logistic_fees,
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
        assert "points" in res
        assert len(res["points"]) == 7
        today_str = timezone.localdate().isoformat()
        today_point = [p for p in res["points"] if p["date"] == today_str][0]
        assert float(today_point["revenue"]) == 400.0

    def test_sales_draft_orders(self):
        customer = CustomerFactory()
        SalesOrder.objects.create(customer=customer, total_amount=Decimal("100.00"), status=SalesOrder.Status.DRAFT)

        res = get_sales_draft_orders()
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["total_amount"] == "100.00"
        assert "items_summary" in res["top_items"][0]
        assert isinstance(res["top_items"][0]["total_amount"], str)

    def test_sales_pending_fulfillment(self):
        customer = CustomerFactory()
        SalesOrder.objects.create(customer=customer, total_amount=Decimal("150.00"), status=SalesOrder.Status.PENDING)

        res = get_sales_pending_fulfillment()
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["total_amount"] == "150.00"
        assert "items_summary" in res["top_items"][0]
        assert isinstance(res["top_items"][0]["total_amount"], str)

    def test_purchasing_active_po_count(self):
        supplier = SupplierFactory()
        PurchaseOrder.objects.create(
            vendor=supplier, total_amount=Decimal("100.00"), status=PurchaseOrder.Status.PENDING
        )
        PurchaseOrder.objects.create(vendor=supplier, total_amount=Decimal("200.00"), status=PurchaseOrder.Status.DRAFT)

        res = get_purchasing_active_po_count()
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["active_po_count"] == 1
        assert res["total_pending_amount"] == "100.00"
        assert "items_summary" in res["top_items"][0]
        assert "expected_delivery_date" in res["top_items"][0]

    def test_purchasing_draft_orders(self):
        supplier = SupplierFactory()
        PurchaseOrder.objects.create(vendor=supplier, total_amount=Decimal("150.00"), status=PurchaseOrder.Status.DRAFT)

        res = get_purchasing_draft_orders()
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["total_amount"] == "150.00"
        assert "items_summary" in res["top_items"][0]
        assert isinstance(res["top_items"][0]["total_amount"], str)

    def test_purchasing_pending_logistic_fees(self):
        Shipment.objects.create(shipment_num="SHIP-02", name="Lô hàng 2", status=Shipment.Status.INSPECTING)
        res = get_purchasing_pending_logistic_fees()
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["shipment_num"] == "SHIP-02"

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
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["name"] == "SE-TRF"
        assert res["top_items"][0]["purpose"] == "transfer"
        assert res["top_items"][0]["route_desc"] == "Kho Nguồn → Kho Đích"
        assert res["top_items"][0]["item_count"] == 1

    def test_finance_cashflow_overview(self):
        today = timezone.localdate()
        # Transaction in period
        CashFlowTransaction.objects.create(
            name="TX-01",
            payment_type="receive",
            amount=Decimal("1500.00"),
            payment_date=today,
            status="posted",
        )
        # Transaction in period
        CashFlowTransaction.objects.create(
            name="TX-02",
            payment_type="pay",
            amount=Decimal("500.00"),
            payment_date=today,
            status="posted",
        )
        # Old transaction (30 days ago, should be excluded from summary)
        CashFlowTransaction.objects.create(
            name="TX-OLD",
            payment_type="receive",
            amount=Decimal("2000.00"),
            payment_date=today - timedelta(days=30),
            status="posted",
        )
        res = get_finance_cashflow_overview()
        assert "summary" in res
        assert "weeks" in res
        assert res["summary"]["receive_total"] == "1500.00"
        assert res["summary"]["pay_total"] == "500.00"
        assert res["summary"]["net_cashflow"] == "1000.00"
        assert res["summary"]["period_label"] == "4 tuần gần nhất"
        assert len(res["weeks"]) == 4

    def test_finance_unpaid_purchase_invoices(self):
        supplier = SupplierFactory()
        PurchaseInvoice.objects.create(
            vendor=supplier, status=PurchaseInvoice.Status.UNPAID, total_amount=Decimal("200.00")
        )
        res = get_finance_unpaid_purchase_invoices()
        assert "buckets" in res
        assert res["total_outstanding"] == "200.00"
        assert res["total_count"] == 1
        assert len(res["buckets"]) == 4
        fresh_bucket = [b for b in res["buckets"] if b["label"] == "0-30 ngày"][0]
        assert float(fresh_bucket["value"]) == 200.00

    def test_finance_unpaid_sales_invoices(self):
        customer = CustomerFactory()
        SalesInvoice.objects.create(
            customer=customer, status=SalesInvoice.Status.UNPAID, total_amount=Decimal("300.00")
        )
        res = get_finance_unpaid_sales_invoices()
        assert "buckets" in res
        assert res["total_outstanding"] == "300.00"
        assert res["total_count"] == 1
        assert len(res["buckets"]) == 4
        fresh_bucket = [b for b in res["buckets"] if b["label"] == "0-30 ngày"][0]
        assert float(fresh_bucket["value"]) == 300.00

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
        assert res["pending_assets_count"] == 0
        assert res["total_depreciation_amount"] == "100.00"
        assert res["is_done"] is True
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1

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
        assert res["status"] == "calculated"
        assert res["calculated_slips_count"] == 1
        assert res["net_pay_total"] == "4500.00"
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1

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
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["employee_name"] == "Employee 2"

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
        assert res["expiring_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["employee_name"] == "Employee 3"

    def test_hrm_today_attendance_rate(self):
        emp = Employee.objects.create(employee_id="E-05", full_name="Employee 5", employment_status="active")
        Attendance.objects.create(employee=emp, date=date.today(), status="working")
        res = get_hrm_today_attendance_rate()
        assert res["attendance_rate"] == Decimal("100.00")
        assert res["present_count"] == 1
        assert res["absent_count"] == 0

        # Now test with another employee who is absent
        emp_absent = Employee.objects.create(employee_id="E-06", full_name="Employee 6", employment_status="active")
        Attendance.objects.create(employee=emp_absent, date=date.today(), status="paid_leave")
        res = get_hrm_today_attendance_rate()
        assert res["attendance_rate"] == Decimal("50.00")
        assert res["present_count"] == 1
        assert res["absent_count"] == 1

        # Test with 3 employees (1 working, 2 absent) -> 33.33%
        emp_absent_2 = Employee.objects.create(employee_id="E-07", full_name="Employee 7", employment_status="active")
        Attendance.objects.create(employee=emp_absent_2, date=date.today(), status="paid_leave")
        res = get_hrm_today_attendance_rate()
        assert res["attendance_rate"] == Decimal("33.33")

    def test_manufacturing_pending_wo_approval(self):
        item = ItemFactory()
        WorkOrder.objects.create(
            name="WO-01", production_item=item, quantity=10, planned_start_date=date.today(), status="pending_approval"
        )
        res = get_manufacturing_pending_wo_approval()
        assert res["total_count"] == 1

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
        # Create work orders with planned_end_date.
        # Nearing delay (2 days left)
        WorkOrder.objects.create(
            name="WO-03",
            production_item=item,
            quantity=10,
            produced_qty=2,
            planned_start_date=date.today(),
            planned_end_date=date.today() + timedelta(days=2),
            status="in_progress",
        )
        # Far delay (10 days left - should not be included)
        WorkOrder.objects.create(
            name="WO-03-FAR",
            production_item=item,
            quantity=10,
            produced_qty=2,
            planned_start_date=date.today(),
            planned_end_date=date.today() + timedelta(days=10),
            status="in_progress",
        )
        res = get_manufacturing_pending_declarations()
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1
        assert res["top_items"][0]["name"] == "WO-03"
        assert res["top_items"][0]["days_left"] == 2

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
        assert res["pending_completion_count"] == 1
        assert res["total_produced_qty"] == "10.00"
        assert res["total_count"] == 1
        assert len(res["top_items"]) == 1

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
        res = get_warehouse_low_stock_alerts()

        # Assertions
        assert res["total_count"] == 2
        assert len(res["items"]) == 2

        # Verify item_ton warning alert
        alert_ton = [a for a in res["items"] if a["item_code"] == "RAW-TON"][0]
        assert alert_ton["status"] == "warning"
        assert "5" in alert_ton["reason"]

        # Verify item_pcs critical alert (due to UOM fallback < 200, no ADC)
        alert_pcs = [a for a in res["items"] if a["item_code"] == "COMP-PCS"][0]
        assert alert_pcs["status"] == "critical"
        assert "50" in alert_pcs["reason"]

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
            res = get_warehouse_low_stock_alerts()

        # Verified O(1) query count (maximum 4 queries: active warehouses, balances, consumptions, item/uom master data)
        assert len(ctx.captured_queries) <= 5
        assert len(res["items"]) == 10

    def test_selector_total_count_greater_than_five(self):
        customer = CustomerFactory()
        # Create 7 draft orders
        for _ in range(7):
            SalesOrder.objects.create(customer=customer, total_amount=Decimal("100.00"), status=SalesOrder.Status.DRAFT)

        res = get_sales_draft_orders()
        assert len(res["top_items"]) == 5
        assert res["total_count"] == 7

    def test_inventory_pending_entries_with_purpose_filter(self):
        uom = UOMFactory()
        item = ItemFactory(stock_uom=uom)
        wh_src = WarehouseFactory(name="Kho Nguồn 1")
        wh_tgt = WarehouseFactory(name="Kho Đích 1")

        se1 = StockEntry.objects.create(name="SE-REC", purpose="receipt", posting_date=timezone.now(), status="draft")
        se2 = StockEntry.objects.create(name="SE-TRF2", purpose="transfer", posting_date=timezone.now(), status="draft")

        res_receipt = get_inventory_pending_entries(purpose="receipt")
        assert res_receipt["total_count"] == 1
        assert res_receipt["top_items"][0]["purpose"] == "receipt"

        res_all = get_inventory_pending_entries()
        assert res_all["total_count"] == 2

    def test_finance_unpaid_purchase_invoices_remaining_amount(self):
        supplier = SupplierFactory()
        PurchaseInvoice.objects.create(
            vendor=supplier,
            status=PurchaseInvoice.Status.PARTIAL,
            total_amount=Decimal("500.00"),
            paid_amount=Decimal("200.00"),
            due_date=date.today() - timedelta(days=5),
        )
        res = get_finance_unpaid_purchase_invoices()
        assert len(res["top_overdue"]) > 0
        invoice = res["top_overdue"][0]
        assert "remaining_amount" in invoice
        assert invoice["remaining_amount"] == "300.00"
        assert isinstance(invoice["remaining_amount"], str)
        assert invoice["overdue_days"] == 5

    def test_finance_unpaid_sales_invoices_remaining_amount(self):
        customer = CustomerFactory()
        invoice = SalesInvoice.objects.create(
            customer=customer,
            status=SalesInvoice.Status.PARTIAL,
            total_amount=Decimal("1000.00"),
            paid_amount=Decimal("400.00"),
        )
        SalesInvoice.objects.filter(id=invoice.id).update(created_at=timezone.now() - timedelta(days=10))
        res = get_finance_unpaid_sales_invoices()
        assert len(res["top_overdue"]) > 0
        invoice_res = res["top_overdue"][0]
        assert "remaining_amount" in invoice_res
        assert invoice_res["remaining_amount"] == "600.00"
        assert isinstance(invoice_res["remaining_amount"], str)
        assert invoice_res["overdue_days"] == 10

    def test_finance_unpaid_purchase_invoices_n_plus_one_safe(self):
        supplier = SupplierFactory()
        for i in range(10):
            PurchaseInvoice.objects.create(
                vendor=supplier,
                status=PurchaseInvoice.Status.UNPAID,
                total_amount=Decimal("100.00") + i,
                due_date=date.today() - timedelta(days=i),
            )
        with CaptureQueriesContext(connection) as ctx:
            res = get_finance_unpaid_purchase_invoices()
        # 1 query for invoices (+ select_related vendor), 1 query for count
        assert len(ctx.captured_queries) <= 3

    def test_manufacturing_pending_wo_approval_list(self):
        item = ItemFactory()
        # Create 5 WOs
        for i in range(5):
            WorkOrder.objects.create(
                name=f"WO-APP-0{i}",
                production_item=item,
                quantity=10 + i,
                planned_start_date=date.today() + timedelta(days=i),
                status="pending_approval",
            )
        res = get_manufacturing_pending_wo_approval()
        assert "top_items" in res
        assert len(res["top_items"]) == 5
        # Should be sorted by planned_start_date ASC
        assert res["top_items"][0]["code"] == "WO-APP-00"
        assert res["top_items"][0]["product_name"] == item.item_name
        assert res["top_items"][0]["days_to_start"] == 0
        assert res["top_items"][1]["days_to_start"] == 1
        assert res["top_items"][2]["days_to_start"] == 2

    def test_manufacturing_pending_wo_approval_no_n_plus_one(self):
        item = ItemFactory()
        for i in range(20):
            WorkOrder.objects.create(
                name=f"WO-APP-BATCH-{i}",
                production_item=item,
                quantity=10,
                planned_start_date=date.today(),
                status="pending_approval",
            )
        with CaptureQueriesContext(connection) as ctx:
            res = get_manufacturing_pending_wo_approval()
        # 1 query for pending count, 1 query for top 3 pending WOs (including select_related)
        assert len(ctx.captured_queries) <= 2

    def test_items_summary_format(self):
        customer = CustomerFactory()
        uom = UOMFactory()
        item_a = ItemFactory(stock_uom=uom, item_name="Sắt")
        item_b = ItemFactory(stock_uom=uom, item_name="Thép")
        item_c = ItemFactory(stock_uom=uom, item_name="Đồng")

        # Test 1: No lines
        so_empty = SalesOrder.objects.create(
            customer=customer, total_amount=Decimal("0.00"), status=SalesOrder.Status.DRAFT
        )
        res_empty = get_sales_draft_orders()
        assert res_empty["top_items"][0]["items_summary"] == ""

        # Test 2: 1 line
        so_1 = SalesOrder.objects.create(
            customer=customer, total_amount=Decimal("100.00"), status=SalesOrder.Status.DRAFT
        )
        from apps.sales.models import SalesOrderLine

        SalesOrderLine.objects.create(order=so_1, item=item_a, quantity=Decimal("10.0"))
        res_1 = get_sales_draft_orders()
        assert res_1["top_items"][0]["items_summary"] == "Sắt: 10"

        # Test 3: 2 lines
        so_2 = SalesOrder.objects.create(
            customer=customer, total_amount=Decimal("200.00"), status=SalesOrder.Status.DRAFT
        )
        SalesOrderLine.objects.create(order=so_2, item=item_a, quantity=Decimal("10.0"))
        SalesOrderLine.objects.create(order=so_2, item=item_b, quantity=Decimal("5.5"))
        res_2 = get_sales_draft_orders()
        assert res_2["top_items"][0]["items_summary"] == "Sắt: 10, Thép: 5.5"

        # Test 4: 3 lines
        so_3 = SalesOrder.objects.create(
            customer=customer, total_amount=Decimal("300.00"), status=SalesOrder.Status.DRAFT
        )
        SalesOrderLine.objects.create(order=so_3, item=item_a, quantity=Decimal("10.0"))
        SalesOrderLine.objects.create(order=so_3, item=item_b, quantity=Decimal("5.0"))
        SalesOrderLine.objects.create(order=so_3, item=item_c, quantity=Decimal("2.0"))
        res_3 = get_sales_draft_orders()
        assert res_3["top_items"][0]["items_summary"] == "Sắt: 10, Thép: 5 và +1 sản phẩm khác"

    def test_items_summary_no_n_plus_one(self):
        customer = CustomerFactory()
        uom = UOMFactory()
        item = ItemFactory(stock_uom=uom, item_name="Sắt")
        from apps.sales.models import SalesOrderLine

        # Create 5 orders each with 3 lines
        for i in range(5):
            so = SalesOrder.objects.create(
                customer=customer, total_amount=Decimal("100.00"), status=SalesOrder.Status.DRAFT
            )
            for j in range(3):
                SalesOrderLine.objects.create(order=so, item=item, quantity=Decimal("10.0"))

        with CaptureQueriesContext(connection) as ctx:
            res = get_sales_draft_orders()

        # O(1) complexity: 1 count query + 1 query to fetch top 5 sales orders + 1 query for prefetched lines + 1 query for prefetched items
        assert len(ctx.captured_queries) <= 4

    def test_unpaid_purchase_invoices_remaining_amount_is_decimal(self):
        from apps.purchasing.models import PurchaseInvoice

        supplier = SupplierFactory()
        PurchaseInvoice.objects.create(
            vendor=supplier,
            status=PurchaseInvoice.Status.PARTIAL,
            total_amount=Decimal("100000.50"),
            paid_amount=Decimal("30000.25"),
        )
        res = get_finance_unpaid_purchase_invoices()
        assert res["total_outstanding"] == "70000.25"
        assert res["top_overdue"][0]["remaining_amount"] == "70000.25"

    def test_unpaid_sales_invoices_remaining_amount_is_decimal(self):
        from apps.sales.models import SalesInvoice

        customer = CustomerFactory()
        SalesInvoice.objects.create(
            customer=customer,
            status=SalesInvoice.Status.PARTIAL,
            total_amount=Decimal("100000.50"),
            paid_amount=Decimal("30000.25"),
        )
        res = get_finance_unpaid_sales_invoices()
        assert res["total_outstanding"] == "70000.25"
        assert res["top_overdue"][0]["remaining_amount"] == "70000.25"

    def test_finance_cashflow_overview_decimal_format(self):
        # Create transactions
        CashFlowTransaction.objects.create(
            name="TX-DEC-1",
            payment_type="receive",
            amount=Decimal("1500.50"),
            payment_date=date.today(),
            status="posted",
        )
        CashFlowTransaction.objects.create(
            name="TX-DEC-2",
            payment_type="pay",
            amount=Decimal("800.25"),
            payment_date=date.today(),
            status="posted",
        )
        res = get_finance_cashflow_overview()
        assert res["summary"]["receive_total"] == "1500.50"
        assert res["summary"]["pay_total"] == "800.25"
        assert res["summary"]["net_cashflow"] == "700.25"


class TestFormatNum:
    def test_format_num_none(self):
        assert format_num(None) == "0"

    def test_format_num_integer_float(self):
        assert format_num(100.0) == "100"
        assert format_num(Decimal("200")) == "200"

    def test_format_num_decimal_float(self):
        assert format_num(Decimal("123.50")) == "123.5"
        assert format_num(5.0) == "5"

    def test_format_num_decimal_string_input(self):
        assert format_num("42.30") == "42.3"
        assert format_num("10") == "10"
