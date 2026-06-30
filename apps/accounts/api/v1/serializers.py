from rest_framework import serializers

from apps.accounts.models import SystemLog, User


class AuthLoginInputSerializer(serializers.Serializer):
    """Serializer để validate dữ liệu đầu vào của API Login."""

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class AuthTokenOutputSerializer(serializers.Serializer):
    """Serializer để định dạng kết quả token trả về."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user_id = serializers.CharField()
    username = serializers.CharField()
    full_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    permissions = serializers.ListField(child=serializers.CharField())


ACTION_DISPLAY = {
    "create": "đã tạo mới",
    "update": "đã cập nhật",
    "delete": "đã xóa",
    "approve": "đã duyệt",
    "reject": "đã từ chối",
    "cancel": "đã hủy",
    "pay": "đã chi trả",
    "approve_credit_bypass": "đã duyệt vượt hạn mức tín dụng",
}

ACTION_CODE_DISPLAY = {
    # inventory
    "inventory.stock_in": "Tạo phiếu nhập kho",
    "inventory.stock_in_approve": "Duyệt phiếu nhập kho",
    "inventory.stock_issue": "Tạo phiếu xuất kho",
    "inventory.stock_issue_approve": "Duyệt phiếu xuất kho",
    "inventory.stock_transfer": "Tạo phiếu chuyển kho",
    "inventory.stock_transfer_approve": "Duyệt phiếu chuyển kho",
    "inventory.view_log": "Xem nhật ký kho",
    # manufacturing
    "manufacturing.bom_create": "Tạo cấu trúc sản phẩm (BOM)",
    "manufacturing.work_order_create": "Tạo Lệnh sản xuất",
    "manufacturing.work_order_approve": "Duyệt Lệnh sản xuất",
    "manufacturing.view_log": "Xem nhật ký sản xuất",
    # purchasing
    "purchasing.order_create": "Tạo đơn mua hàng",
    "purchasing.order_approve": "Duyệt đơn mua hàng",
    "purchasing.view_log": "Xem nhật ký mua hàng",
    # sales
    "sales.order_create": "Tạo đơn bán hàng",
    "sales.order_approve": "Duyệt đơn bán hàng",
    "sales.view_log": "Xem nhật ký bán hàng",
    # finance
    "finance.cash_flow_create": "Tạo dòng tiền",
    "finance.pay_invoice": "Quyết toán chi lương",
    "finance.collect_sales_invoice": "Quyết toán thu bán hàng",
    "finance.view_log": "Xem nhật ký tài chính",
    # hrm
    "hrm.employee_create": "Tạo nhân viên",
    "hrm.view_log": "Xem nhật ký nhân sự",
    # accounts
    "accounts.add_user": "Tạo tài khoản",
    "accounts.view_system_log": "Xem nhật ký hệ thống",
    # un-prefixed actions
    "run_depreciation": "Khấu hao tài sản cố định",
    "reject_logistics": "Từ chối vận chuyển",
    "approve_logistics": "Duyệt vận chuyển",
}

TABLE_DISPLAY = {
    "stock_entry": "Phiếu kho",
    "sales_order": "Đơn bán hàng",
    "purchase_order": "Đơn mua hàng",
    "salary_slip": "Bảng lương",
    "employee": "Nhân viên",
    "user": "Tài khoản",
    "cash_flow_transaction": "Giao dịch dòng tiền",
    "shipment": "Lô hàng vận chuyển",
    "fixed_asset_depreciation_log": "Khấu hao TSCĐ",
    "customer": "Khách hàng",
    "supplier": "Nhà cung cấp",
    "bom": "Định mức vật tư (BOM)",
    "work_order": "Lệnh sản xuất",
    "fixed_asset": "Tài sản cố định",
    "leave_request": "Đơn xin nghỉ phép",
    "employee_document": "Hồ sơ đính kèm",
    "employment_contract": "Hợp đồng lao động",
    "attendance": "Bản ghi chấm công",
    "reward_record": "Khen thưởng",
    "discipline_record": "Kỷ luật",
    "public_holiday": "Ngày nghỉ lễ",
}


class SystemLogUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "employee_id", "full_name"]

    def get_full_name(self, obj):
        if obj.employee_id:
            from apps.master_data.models import Employee

            emp = Employee.objects.filter(employee_id=obj.employee_id).first()
            if emp:
                return emp.full_name
        return None


class SystemLogListSerializer(serializers.ModelSerializer):
    user = SystemLogUserSerializer(read_only=True)
    action_display = serializers.SerializerMethodField()
    table_display = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()
    record_code = serializers.SerializerMethodField()

    class Meta:
        model = SystemLog
        fields = [
            "id",
            "timestamp",
            "user",
            "user_repr",
            "action",
            "action_display",
            "table_name",
            "table_display",
            "record_id",
            "record_code",
            "message",
            "changes",
        ]

    def get_action_display(self, obj):
        # 1. Check action + table combination first for user friendly labels
        combo_key = f"{obj.action}:{obj.table_name}"
        combo_display = {
            "approve_credit_bypass:sales_order": "Duyệt vượt hạn mức nợ",
            "reject_purchase:fixed_asset": "Từ chối mua TSCĐ",
            "reject_dispose:fixed_asset": "Từ chối thanh lý TSCĐ",
            "request_dispose:fixed_asset": "Yêu cầu thanh lý TSCĐ",
            "request_dispose_zero_value:fixed_asset": "Yêu cầu thanh lý TSCĐ giá trị 0",
            "auto_activate:fixed_asset": "Tự động kích hoạt TSCĐ",
            "auto_dispose:fixed_asset": "Tự động thanh lý TSCĐ",
            "terminated_by_discipline:discipline_record": "Sa thải do kỷ luật",
        }
        if combo_key in combo_display:
            return combo_display[combo_key]

        if obj.action in ACTION_CODE_DISPLAY:
            return ACTION_CODE_DISPLAY[obj.action]

        # 2. Dynamic generation of Action Badge label: Action Verb (Noun form) + Table Name
        action_nouns = {
            "create": "Tạo",
            "update": "Cập nhật",
            "delete": "Xóa",
            "approve": "Duyệt",
            "reject": "Từ chối",
            "cancel": "Hủy",
            "pay": "Thanh toán",
            "change_password": "Đổi mật khẩu",
            "run_depreciation": "Trích khấu hao",
            "reject_logistics": "Từ chối vận chuyển",
            "approve_logistics": "Duyệt vận chuyển",
            "declare_production": "Khai báo sản xuất",
            "complete": "Hoàn tất",
        }

        parts = obj.action.split(".")
        suffix = parts[-1] if parts else obj.action

        action_prefix = action_nouns.get(suffix) or action_nouns.get(obj.action)

        if action_prefix:
            table_name_vn = self.get_table_display(obj)
            if table_name_vn:
                if table_name_vn.isupper():
                    return f"{action_prefix} {table_name_vn}"
                else:
                    return f"{action_prefix} {table_name_vn[0].lower()}{table_name_vn[1:]}"
            return action_prefix

        return ACTION_DISPLAY.get(suffix, obj.action)

    def get_table_display(self, obj):
        return TABLE_DISPLAY.get(obj.table_name, obj.table_name)

    def _resolve_raw_code(self, obj):
        try:
            from django.apps import apps

            model_map = {
                "sales_order": ("sales", "SalesOrder"),
                "purchase_order": ("purchasing", "PurchaseOrder"),
                "stock_entry": ("inventory", "StockEntry"),
                "employee": ("master_data", "Employee"),
                "user": ("accounts", "User"),
                "salary_slip": ("finance", "SalarySlip"),
                "shipment": ("purchasing", "Shipment"),
                "customer": ("crm", "Customer"),
                "supplier": ("procurement", "Supplier"),
                "bom": ("master_data", "BOM"),
                "work_order": ("master_data", "WorkOrder"),
                "fixed_asset": ("finance", "FixedAsset"),
                "leave_request": ("hrm", "LeaveRequest"),
                "employee_document": ("hrm", "EmployeeDocument"),
                "employment_contract": ("hrm", "EmploymentContract"),
                "attendance": ("hrm", "Attendance"),
                "reward_record": ("hrm", "RewardRecord"),
                "discipline_record": ("hrm", "DisciplineRecord"),
                "public_holiday": ("hrm", "PublicHoliday"),
            }
            if obj.table_name in model_map:
                app_label, model_name = model_map[obj.table_name]
                model = apps.get_model(app_label, model_name)
                record = model.objects.filter(id=obj.record_id).first()
                if record:
                    if hasattr(record, "order_code"):
                        return record.order_code
                    if hasattr(record, "voucher_code"):
                        return record.voucher_code
                    if hasattr(record, "shipment_num"):
                        return record.shipment_num
                    if hasattr(record, "contract_no"):
                        return record.contract_no
                    if hasattr(record, "asset_code"):
                        return record.asset_code
                    if hasattr(record, "employee_id"):
                        return record.employee_id
                    if hasattr(record, "customer_name"):
                        return record.customer_name
                    if hasattr(record, "supplier_name"):
                        return record.supplier_name
                    if hasattr(record, "employee") and hasattr(record, "date"):
                        return f"{record.employee.full_name} ({record.date})"
                    if hasattr(record, "employee") and hasattr(record, "start_date"):
                        return f"{record.employee.full_name} ({record.start_date})"
                    if hasattr(record, "employee") and record.employee:
                        return record.employee.full_name
                    if hasattr(record, "username"):
                        return record.username
                    if hasattr(record, "code"):
                        return record.code
                    if hasattr(record, "name"):
                        return record.name
                    if hasattr(record, "title"):
                        return record.title
        except Exception:
            pass
        return None

    def get_record_code(self, obj):
        # 1. Try to return pre-populated static record_code
        if obj.record_code:
            return obj.record_code

        # 2. Backward compatibility fallback
        if not obj.record_id:
            return None
        code = self._resolve_raw_code(obj)
        if not code:
            code = obj.record_id
        if code:
            import re

            uuid_pattern = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$")
            if uuid_pattern.match(str(code)):
                return str(code)[:8].upper()
            return str(code)
        return None

    def get_message(self, obj):
        username = "Hệ thống"
        if obj.user:
            username = self.get_user_friendly_name(obj.user)
        elif obj.user_repr:
            username = obj.user_repr

        # Action verbs for clean natural sentence building
        verbs = {
            "create": "tạo mới",
            "update": "cập nhật",
            "delete": "xóa",
            "approve": "duyệt",
            "reject": "từ chối",
            "cancel": "hủy",
            "pay": "chi trả",
            "run_depreciation": "chạy",
            "reject_logistics": "từ chối vận chuyển",
            "approve_logistics": "duyệt vận chuyển",
            "change_password": "đổi mật khẩu",
            "auto_activate": "tự động kích hoạt",
            "auto_dispose": "tự động thanh lý",
            "reject_purchase": "từ chối mua",
            "reject_dispose": "từ chối thanh lý",
            "request_dispose": "yêu cầu thanh lý",
            "request_dispose_zero_value": "yêu cầu thanh lý giá trị 0",
            "terminated_by_discipline": "sa thải do kỷ luật",
            "declare_production": "khai báo sản xuất",
            "complete": "hoàn tất",
            "approve_credit_bypass": "duyệt vượt hạn mức nợ",
        }

        action_verb = "thao tác trên"
        parts = obj.action.split(".")
        suffix = parts[-1] if parts else obj.action
        if suffix in verbs:
            action_verb = verbs[suffix]
        elif obj.action in verbs:
            action_verb = verbs[obj.action]

        table_text = self.get_table_display(obj)
        record_code = self.get_record_code(obj)
        record_text = record_code or obj.record_id

        if record_text:
            return f"{username} đã {action_verb} {table_text} ({record_text})"
        return f"{username} đã {action_verb} {table_text}"

    def get_user_friendly_name(self, user):
        if user.employee_id:
            from apps.master_data.models import Employee

            emp = Employee.objects.filter(employee_id=user.employee_id).first()
            if emp:
                return emp.full_name
        return user.username

    def get_changes(self, obj):
        if not obj.old_value and not obj.new_value:
            return None
        old_data = obj.old_value or {}
        new_data = obj.new_value or {}
        all_keys = set(old_data.keys()) | set(new_data.keys())

        changes = {}
        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return changes if changes else None


class UserOutputSerializer(serializers.Serializer):
    """Serializer định dạng kết quả tài khoản người dùng."""

    id = serializers.UUIDField()
    username = serializers.CharField()
    employee_id = serializers.CharField()
    employee_name = serializers.SerializerMethodField()
    direct_permissions = serializers.SerializerMethodField()
    all_permissions = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()
    last_login = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()

    def get_employee_name(self, obj):
        employee_map = self.context.get("employee_map")
        if employee_map and obj.employee_id:
            return employee_map.get(obj.employee_id, "")
        if obj.employee_id:
            from apps.master_data.models import Employee

            emp = Employee.objects.filter(employee_id=obj.employee_id).first()
            return emp.full_name if emp else ""
        return ""

    def get_direct_permissions(self, obj):
        return list(obj.direct_permissions.values_list("permission__code", flat=True))

    def get_all_permissions(self, obj):
        return list(obj.direct_permissions.values_list("permission__code", flat=True))


class UserCreateInputSerializer(serializers.Serializer):
    """Serializer validate đầu vào khi tạo tài khoản người dùng."""

    employee_id = serializers.CharField(max_length=50, required=True)
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(max_length=128, required=True)
    direct_permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class UserUpdateInputSerializer(serializers.Serializer):
    """Serializer validate đầu vào khi cập nhật tài khoản người dùng."""

    direct_permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class UserChangePasswordInputSerializer(serializers.Serializer):
    """Serializer validate đầu vào khi đổi mật khẩu."""

    password = serializers.CharField(max_length=128, required=True)


class PermissionOutputSerializer(serializers.Serializer):
    """Serializer định dạng thông tin quyền hạn."""

    code = serializers.CharField()
    name = serializers.CharField()


class EmployeeUnlinkedOutputSerializer(serializers.Serializer):
    """Serializer định dạng thông tin nhân viên chưa có tài khoản."""

    employee_id = serializers.CharField()
    full_name = serializers.CharField()
    email = serializers.EmailField(allow_blank=True, allow_null=True)
