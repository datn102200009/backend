"""
Views for hrm API v1.

Orchestrates request processing: validate input, call services/selectors, return response.
"""

from datetime import date

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.common.services import create_system_log
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.finance.models import SalarySlip
from apps.hrm.api.v1.serializers import (
    AttendanceBatchInputSerializer,
    AttendanceOutputSerializer,
    CancelRecordInputSerializer,
    ContractCreateOrRenewInputSerializer,
    ContractRenewInputSerializer,
    ContractTerminateInputSerializer,
    DisciplineRecordCreateInputSerializer,
    DisciplineRecordOutputSerializer,
    DisciplineRecordUpdateInputSerializer,
    EmployeeAdjustSalaryInputSerializer,
    EmployeeCreateInputSerializer,
    EmployeeDetailOutputSerializer,
    EmployeeOutputSerializer,
    EmployeeUpdateInputSerializer,
    EmployeeWithContractCreateInputSerializer,
    EmploymentContractOutputSerializer,
    LeaveRequestApproveInputSerializer,
    LeaveRequestCreateInputSerializer,
    LeaveRequestOutputSerializer,
    PartialSalarySlipInputSerializer,
    PublicHolidaySerializer,
    RewardRecordCreateInputSerializer,
    RewardRecordOutputSerializer,
    RewardRecordUpdateInputSerializer,
    SalarySlipBulkConfirmInputSerializer,
    SalarySlipConfirmInputSerializer,
    SalarySlipInitializeInputSerializer,
    SalarySlipOutputSerializer,
)
from apps.hrm.models import Attendance, DisciplineRecord, EmploymentContract, LeaveRequest, PublicHoliday, RewardRecord
from apps.hrm.selectors import employee_get_detail_with_relations
from apps.hrm.services import (
    attendance_batch_record,
    contract_create_or_renew,
    contract_renew,
    contract_terminate,
    create_partial_salary_slip,
    discipline_record_approve,
    discipline_record_cancel,
    discipline_record_create,
    discipline_record_delete,
    discipline_record_update,
    employee_adjust_salary_apply,
    employee_create_with_contract,
    employee_update,
    leave_request_approve,
    leave_request_create,
    payroll_bulk_calculate,
    payroll_bulk_submit_for_review,
    payroll_calculate_salary,
    payroll_initialize_period,
    payroll_submit_for_review,
    public_holiday_create,
    public_holiday_delete,
    public_holiday_update,
    reward_record_approve,
    reward_record_cancel,
    reward_record_create,
    reward_record_delete,
    reward_record_update,
)
from apps.master_data.models import Employee

# =============================================================================
# EMPLOYEE VIEWS
# =============================================================================


@api_view(["GET"])
def employee_list_view(request):
    """
    Xem danh sách nhân viên.
    Hỗ trợ search (tên/mã), status filter, và phân trang limit/offset.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.view_employee")

    search = request.query_params.get("search")
    status_param = request.query_params.get("status")

    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        limit = min(limit, 100)
    except ValueError:
        limit = 20
        offset = 0

    qs = Employee.objects.all().order_by("employee_id")

    if search:
        qs = qs.filter(full_name__icontains=search) | qs.filter(employee_id__icontains=search)

    if status_param:
        qs = qs.filter(employment_status=status_param)

    count = qs.count()
    results = qs[offset : offset + limit]

    serializer = EmployeeOutputSerializer(results, many=True)
    return Response(
        {
            "count": count,
            "next": None,
            "previous": None,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def employee_create_view(request):
    """
    Tạo mới một nhân viên (và tài khoản người dùng, hợp đồng lao động nếu được yêu cầu).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.add_employee")

    serializer = EmployeeWithContractCreateInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Tách contract_data
    contract_data = {
        "contract_no": data.get("contract_no"),
        "contract_type": data.get("contract_type"),
        "start_date": data.get("contract_start_date"),
        "end_date": data.get("contract_end_date"),
        "note": data.get("contract_note"),
        "file_url": data.get("contract_file_url"),
    }
    if "contract_salary_base" in data:
        contract_data["salary_base"] = data["contract_salary_base"]

    try:
        employee, contract = employee_create_with_contract(
            data=data,
            contract_data=contract_data,
            creator=user,
        )
    except IntegrityError:
        raise ValidationException("Dữ liệu bị trùng lặp hoặc vi phạm ràng buộc CSDL. Vui lòng kiểm tra lại.")

    emp_out = EmployeeOutputSerializer(employee).data
    resp = {"employee": emp_out}
    if contract:
        resp["contract"] = EmploymentContractOutputSerializer(contract).data
    return Response(resp, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def employee_detail_view(request, pk):
    """
    Xem chi tiết thông tin nhân viên (bao gồm các quan hệ prefetch).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.view_employee")

    try:
        employee = employee_get_detail_with_relations(employee_id=pk)
    except Employee.DoesNotExist:
        raise NotFoundException("Không tìm thấy nhân viên")

    serializer = EmployeeDetailOutputSerializer(employee)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["PATCH"])
@throttle_classes([UserRateThrottle])
def employee_update_view(request, pk):
    """
    Cập nhật hồ sơ nhân viên.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_employee")

    try:
        employee = Employee.objects.get(id=pk)
    except Employee.DoesNotExist:
        raise NotFoundException("Không tìm thấy nhân viên")

    serializer = EmployeeUpdateInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        updated_employee = employee_update(
            employee=employee,
            data=serializer.validated_data,
            updater=user,
        )
    except IntegrityError:
        raise ValidationException("Dữ liệu bị trùng lặp hoặc vi phạm ràng buộc CSDL.")

    out_serializer = EmployeeOutputSerializer(updated_employee)
    return Response(out_serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def employee_adjust_salary_view(request, pk):
    """
    Điều chỉnh lương cơ bản của nhân viên (áp dụng trực tiếp).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.adjust_salary")

    serializer = EmployeeAdjustSalaryInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    result = employee_adjust_salary_apply(
        employee_id=pk,
        new_salary_base=serializer.validated_data.get("new_salary_base"),
        reason=serializer.validated_data.get("reason"),
        actor=user,
    )

    response_data = {
        "contract": EmploymentContractOutputSerializer(result["contract"]).data,
        "affected_payslips": SalarySlipOutputSerializer(result["affected_payslips"], many=True).data,
    }
    return Response(response_data, status=status.HTTP_200_OK)


# =============================================================================
# CONTRACT VIEWS
# =============================================================================


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def contract_create_or_renew_view(request):
    """
    Tạo hoặc gia hạn hợp đồng lao động của nhân viên.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.add_employmentcontract")

    serializer = ContractCreateOrRenewInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    employee_id = str(data.pop("employee_id"))

    contract = contract_create_or_renew(
        employee_id=employee_id,
        contract_data=data,
        creator=user,
    )

    out_serializer = EmploymentContractOutputSerializer(contract)
    return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def contract_terminate_view(request, pk):
    """
    Chấm dứt hợp đồng lao động (vô hiệu hóa user, cập nhật employee sang inactive).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_employmentcontract")

    serializer = ContractTerminateInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    contract = contract_terminate(
        contract_id=pk,
        termination_date=data.get("termination_date"),
        reason=data.get("reason"),
        terminator=user,
        file_url=data.get("file_url"),
        is_lawful=data.get("is_lawful", True),
        unused_leave_days=data.get("unused_leave_days", 0.0),
        standard_working_days=data.get("standard_working_days", 26),
        unnotified_days=data.get("unnotified_days", 0),
    )

    out_serializer = EmploymentContractOutputSerializer(contract)
    return Response(out_serializer.data, status=status.HTTP_200_OK)


# =============================================================================
# ATTENDANCE VIEWS
# =============================================================================


@api_view(["GET"])
def attendance_list_view(request):
    """
    Xem danh sách chấm công.
    Hỗ trợ lọc theo date và employee_id, kèm phân trang.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.view_attendance")

    date_param = request.query_params.get("date")
    employee_id = request.query_params.get("employee_id")

    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        limit = min(limit, 100)
    except ValueError:
        limit = 20
        offset = 0

    qs = Attendance.objects.all().select_related("employee").order_by("-date", "employee__employee_id")

    if date_param:
        qs = qs.filter(date=date_param)
    if employee_id:
        qs = qs.filter(employee_id=employee_id)

    count = qs.count()
    results = qs[offset : offset + limit]

    serializer = AttendanceOutputSerializer(results, many=True)
    return Response(
        {
            "count": count,
            "next": None,
            "previous": None,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def attendance_batch_view(request):
    """
    Chấm công hàng loạt cho nhân viên vào một ngày cụ thể.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.add_attendance")

    serializer = AttendanceBatchInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    attendances = attendance_batch_record(
        date=data.get("date"),
        records=data.get("records"),
        creator=user,
    )

    out_serializer = AttendanceOutputSerializer(attendances, many=True)
    return Response(out_serializer.data, status=status.HTTP_201_CREATED)


# =============================================================================
# LEAVE REQUEST VIEWS
# =============================================================================


@api_view(["GET"])
def leave_request_list_view(request):
    """
    Xem danh sách đơn xin nghỉ phép.
    Lọc theo status và employee_id, kèm phân trang.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.view_leaverequest")

    status_param = request.query_params.get("status")
    employee_id = request.query_params.get("employee_id")

    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        limit = min(limit, 100)
    except ValueError:
        limit = 20
        offset = 0

    qs = LeaveRequest.objects.all().select_related("employee", "approved_by").order_by("-created_at", "id")

    if status_param:
        qs = qs.filter(status=status_param)
    if employee_id:
        qs = qs.filter(employee_id=employee_id)

    count = qs.count()
    results = qs[offset : offset + limit]

    serializer = LeaveRequestOutputSerializer(results, many=True)
    return Response(
        {
            "count": count,
            "next": None,
            "previous": None,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def leave_request_create_view(request):
    """
    Tạo đơn xin nghỉ phép (mặc định pending).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.add_leaverequest")

    serializer = LeaveRequestCreateInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    employee_id = str(data.pop("employee_id"))

    leave_request = leave_request_create(
        employee_id=employee_id,
        data=data,
        creator=user,
    )

    out_serializer = LeaveRequestOutputSerializer(leave_request)
    return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def leave_request_approve_view(request, pk):
    """
    Duyệt hoặc từ chối đơn xin nghỉ phép.
    Nếu Duyệt: tự động đồng bộ sang bảng Attendance.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_leaverequest")

    try:
        leave_request = LeaveRequest.objects.get(id=pk)
    except LeaveRequest.DoesNotExist:
        raise NotFoundException("Đơn xin nghỉ phép không tồn tại")

    serializer = LeaveRequestApproveInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    action = serializer.validated_data["action"]

    if action == "approve":
        updated_request = leave_request_approve(
            leave_request_id=pk,
            approved_by_user_id=str(user.id),
            approved_by=user,
        )
    else:  # reject
        if leave_request.status != "pending":
            raise ValidationException(f"Đơn xin nghỉ phép đã ở trạng thái: {leave_request.status}")

        old_status = leave_request.status
        leave_request.status = "rejected"
        leave_request.approved_by = user
        leave_request.approved_at = timezone.now()
        leave_request.save(update_fields=["status", "approved_by", "approved_at"])

        create_system_log(
            user=user,
            action="update",
            table_name="leave_request",
            record_id=str(leave_request.id),
            old_value={"status": old_status},
            new_value={
                "status": "rejected",
                "approved_by_id": str(user.id),
                "approved_at": str(leave_request.approved_at),
            },
            allowed_permissions=["hrm.view_log"],
        )
        updated_request = leave_request

    out_serializer = LeaveRequestOutputSerializer(updated_request)
    return Response(out_serializer.data, status=status.HTTP_200_OK)


# =============================================================================
# SALARY SLIP VIEWS
# =============================================================================


@api_view(["GET"])
def salary_slip_list_view(request):
    """
    Xem danh sách phiếu lương.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.view_salaryslip")

    period = request.query_params.get("salary_period")
    employee_id = request.query_params.get("employee_id")
    status_param = request.query_params.get("status")

    qs = SalarySlip.objects.all().select_related("employee").order_by("-salary_period", "employee__employee_id")

    if period:
        qs = qs.filter(salary_period=period)
    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if status_param:
        qs = qs.filter(status=status_param)

    serializer = SalarySlipOutputSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def salary_periods_list_view(request):
    """
    Xem danh sách các kỳ lương tồn tại.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.view_salaryslip")

    periods = SalarySlip.objects.values_list("salary_period", flat=True).distinct().order_by("-salary_period")
    periods = [p for p in periods if p]
    return Response(periods, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def salary_slip_initialize_view(request):
    """
    Khởi tạo hàng loạt phiếu lương cho tất cả nhân sự active trong một kỳ lương.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.add_salaryslip")

    serializer = SalarySlipInitializeInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    slips = payroll_initialize_period(
        salary_period=serializer.validated_data["salary_period"],
        creator=user,
    )

    out_serializer = SalarySlipOutputSerializer(slips, many=True)
    return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def salary_slip_calculate_view(request, pk):
    """
    Tính toán chi tiết các thành phần phiếu lương của nhân viên.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.change_salaryslip")

    try:
        slip = SalarySlip.objects.get(id=pk)
    except SalarySlip.DoesNotExist:
        raise NotFoundException("Không tìm thấy phiếu lương")

    updated_slip = payroll_calculate_salary(
        salary_slip_id=pk,
        creator=user,
    )

    out_serializer = SalarySlipOutputSerializer(updated_slip)
    return Response(out_serializer.data, status=status.HTTP_200_OK)


# =============================================================================
# REWARD & DISCIPLINE VIEWS
# =============================================================================


@api_view(["GET", "POST"])
@throttle_classes([UserRateThrottle])
def reward_list_create_view(request):
    """
    Xem danh sách hoặc ghi nhận khen thưởng của nhân viên.
    Hỗ trợ lọc nâng cao và phân trang.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_rewardrecord")
        employee_id = request.query_params.get("employee_id")
        status_param = request.query_params.get("status")
        reward_type = request.query_params.get("reward_type")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
            limit = min(limit, 100)
        except ValueError:
            limit = 20
            offset = 0

        qs = RewardRecord.objects.all().select_related("employee").order_by("-reward_date", "-created_at", "id")

        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if reward_type:
            qs = qs.filter(reward_type=reward_type)

        if date_from or date_to:
            try:
                from datetime import datetime

                if date_from:
                    df = datetime.strptime(date_from, "%Y-%m-%d").date()
                else:
                    df = None
                if date_to:
                    dt = datetime.strptime(date_to, "%Y-%m-%d").date()
                else:
                    dt = None

                if df and dt and df > dt:
                    raise ValidationException("date_from không được lớn hơn date_to")

                if df:
                    qs = qs.filter(reward_date__gte=df)
                if dt:
                    qs = qs.filter(reward_date__lte=dt)
            except ValueError:
                raise ValidationException("Định dạng ngày không hợp lệ. Sử dụng YYYY-MM-DD.")

        count = qs.count()
        results = qs[offset : offset + limit]
        serializer = RewardRecordOutputSerializer(results, many=True)
        return Response(
            {
                "count": count,
                "next": None,
                "previous": None,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    elif request.method == "POST":
        PermissionChecker.check_permission(user, "hrm.add_rewardrecord")
        serializer = RewardRecordCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        employee_id = str(data.pop("employee_id"))

        reward = reward_record_create(
            employee_id=employee_id,
            data=data,
            creator=user,
        )

        out_serializer = RewardRecordOutputSerializer(reward)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@throttle_classes([UserRateThrottle])
def reward_detail_update_delete_view(request, pk):
    """
    Xem chi tiết, cập nhật hoặc xóa khen thưởng.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        reward = RewardRecord.objects.select_related("employee").get(id=pk)
    except RewardRecord.DoesNotExist:
        raise NotFoundException("Không tìm thấy khen thưởng")

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_rewardrecord")
        serializer = RewardRecordOutputSerializer(reward)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "PATCH":
        PermissionChecker.check_permission(user, "hrm.change_rewardrecord")
        serializer = RewardRecordUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_reward = reward_record_update(
            reward_id=str(reward.id),
            data=serializer.validated_data,
            updater=user,
        )

        return Response(RewardRecordOutputSerializer(updated_reward).data, status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        PermissionChecker.check_permission(user, "hrm.delete_rewardrecord")
        reward_record_delete(
            reward_id=str(reward.id),
            deleter=user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def reward_cancel_view(request, pk):
    """
    Hủy khen thưởng.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_rewardrecord")
    serializer = CancelRecordInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    reward = reward_record_cancel(
        reward_id=pk,
        user=user,
        reason=serializer.validated_data.get("reason"),
    )

    return Response(RewardRecordOutputSerializer(reward).data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@throttle_classes([UserRateThrottle])
def discipline_list_create_view(request):
    """
    Xem danh sách hoặc ghi nhận kỷ luật của nhân viên.
    Hỗ trợ lọc nâng cao và phân trang.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_disciplinerecord")
        employee_id = request.query_params.get("employee_id")
        status_param = request.query_params.get("status")
        discipline_type = request.query_params.get("discipline_type")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
            limit = min(limit, 100)
        except ValueError:
            limit = 20
            offset = 0

        qs = DisciplineRecord.objects.all().select_related("employee").order_by("-discipline_date", "-created_at", "id")

        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if discipline_type:
            qs = qs.filter(discipline_type=discipline_type)

        if date_from or date_to:
            try:
                from datetime import datetime

                if date_from:
                    df = datetime.strptime(date_from, "%Y-%m-%d").date()
                else:
                    df = None
                if date_to:
                    dt = datetime.strptime(date_to, "%Y-%m-%d").date()
                else:
                    dt = None

                if df and dt and df > dt:
                    raise ValidationException("date_from không được lớn hơn date_to")

                if df:
                    qs = qs.filter(discipline_date__gte=df)
                if dt:
                    qs = qs.filter(discipline_date__lte=dt)
            except ValueError:
                raise ValidationException("Định dạng ngày không hợp lệ. Sử dụng YYYY-MM-DD.")

        count = qs.count()
        results = qs[offset : offset + limit]
        serializer = DisciplineRecordOutputSerializer(results, many=True)
        return Response(
            {
                "count": count,
                "next": None,
                "previous": None,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    elif request.method == "POST":
        PermissionChecker.check_permission(user, "hrm.add_disciplinerecord")
        serializer = DisciplineRecordCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        employee_id = str(data.pop("employee_id"))

        discipline = discipline_record_create(
            employee_id=employee_id,
            data=data,
            creator=user,
        )

        out_serializer = DisciplineRecordOutputSerializer(discipline)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@throttle_classes([UserRateThrottle])
def discipline_detail_update_delete_view(request, pk):
    """
    Xem chi tiết, cập nhật hoặc xóa kỷ luật.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        discipline = DisciplineRecord.objects.select_related("employee").get(id=pk)
    except DisciplineRecord.DoesNotExist:
        raise NotFoundException("Không tìm thấy kỷ luật")

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_disciplinerecord")
        serializer = DisciplineRecordOutputSerializer(discipline)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "PATCH":
        PermissionChecker.check_permission(user, "hrm.change_disciplinerecord")
        serializer = DisciplineRecordUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_discipline = discipline_record_update(
            discipline_id=str(discipline.id),
            data=serializer.validated_data,
            updater=user,
        )

        return Response(DisciplineRecordOutputSerializer(updated_discipline).data, status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        PermissionChecker.check_permission(user, "hrm.delete_disciplinerecord")
        discipline_record_delete(
            discipline_id=str(discipline.id),
            deleter=user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def discipline_cancel_view(request, pk):
    """
    Hủy kỷ luật.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_disciplinerecord")
    serializer = CancelRecordInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    discipline = discipline_record_cancel(
        discipline_id=pk,
        user=user,
        reason=serializer.validated_data.get("reason"),
    )

    return Response(DisciplineRecordOutputSerializer(discipline).data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@throttle_classes([UserRateThrottle])
def public_holiday_list_create_view(request):
    """
    Xem danh sách hoặc khai báo ngày nghỉ lễ.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_publicholiday")
        qs = PublicHoliday.objects.all().order_by("-start_date", "id")
        year = request.query_params.get("year")
        if year:
            try:
                year_val = int(year)
                from datetime import date, timedelta

                from django.db.models import DateField, DurationField, ExpressionWrapper, F

                year_start_date = date(year_val, 1, 1)
                year_end_date = date(year_val, 12, 31)

                duration_expr = ExpressionWrapper(F("days") * timedelta(days=1), output_field=DurationField())
                end_date_expr = ExpressionWrapper(
                    F("start_date") + duration_expr - timedelta(days=1), output_field=DateField()
                )

                qs = qs.annotate(end_date=end_date_expr).filter(
                    start_date__lte=year_end_date, end_date__gte=year_start_date
                )
            except ValueError:
                pass
        serializer = PublicHolidaySerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        PermissionChecker.check_permission(user, "hrm.add_publicholiday")
        serializer = PublicHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            holiday = public_holiday_create(
                name=serializer.validated_data["name"],
                start_date=serializer.validated_data["start_date"],
                days=serializer.validated_data.get("days", 1),
                description=serializer.validated_data.get("description", ""),
                creator=user,
            )
        except IntegrityError:
            raise ValidationException("Ngày nghỉ lễ này đã tồn tại trong hệ thống.")

        out_serializer = PublicHolidaySerializer(holiday)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@throttle_classes([UserRateThrottle])
def public_holiday_detail_update_delete_view(request, pk):
    """
    Xem chi tiết, cập nhật hoặc xóa ngày nghỉ lễ.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        holiday = PublicHoliday.objects.get(id=pk)
    except PublicHoliday.DoesNotExist:
        raise NotFoundException("Không tìm thấy ngày nghỉ lễ")

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_publicholiday")
        serializer = PublicHolidaySerializer(holiday)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ["PUT", "PATCH"]:
        PermissionChecker.check_permission(user, "hrm.change_publicholiday")
        serializer = PublicHolidaySerializer(holiday, data=request.data, partial=(request.method == "PATCH"))
        serializer.is_valid(raise_exception=True)
        try:
            updated_holiday = public_holiday_update(
                holiday=holiday,
                data=serializer.validated_data,
                updater=user,
            )
        except IntegrityError:
            raise ValidationException("Ngày nghỉ lễ này đã tồn tại trong hệ thống.")

        out_serializer = PublicHolidaySerializer(updated_holiday)
        return Response(out_serializer.data, status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        PermissionChecker.check_permission(user, "hrm.delete_publicholiday")
        public_holiday_delete(
            holiday=holiday,
            deleter=user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def reward_approve_view(request, pk):
    """
    Phê duyệt khen thưởng.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_rewardrecord")
    reward = reward_record_approve(user=user, reward_id=pk)
    return Response(RewardRecordOutputSerializer(reward).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def discipline_approve_view(request, pk):
    """
    Phê duyệt kỷ luật.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_disciplinerecord")
    discipline = discipline_record_approve(user=user, discipline_id=pk)
    return Response(DisciplineRecordOutputSerializer(discipline).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def contract_renew_view(request, pk):
    """
    Gia hạn hợp đồng lao động (tái ký), có thể kèm điều chỉnh lương cơ bản.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_employmentcontract")

    try:
        old_contract = EmploymentContract.objects.get(id=pk)
    except EmploymentContract.DoesNotExist:
        raise NotFoundException("Không tìm thấy hợp đồng lao động")

    serializer = ContractRenewInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    result = contract_renew(
        contract_id=pk,
        new_contract_no=data.get("new_contract_no"),
        new_contract_type=data.get("new_contract_type"),
        start_date=data.get("start_date"),
        new_salary_base=data.get("new_salary_base"),
        file_url=data.get("file_url"),
        note=data.get("note"),
        renewer=user,
    )

    resp_data = {
        "contract": EmploymentContractOutputSerializer(result["contract"]).data,
    }
    return Response(resp_data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def partial_salary_slip_create_view(request):
    """
    Tạo phiếu lương cho một phần giai đoạn của kỳ lương.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.add_salaryslip")

    serializer = PartialSalarySlipInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    slip = create_partial_salary_slip(
        employee_id=str(data["employee_id"]),
        period_start=data["period_start"],
        period_end=data["period_end"],
        name=data["name"],
        creator=user,
    )

    out_serializer = SalarySlipOutputSerializer(slip)
    return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def payroll_submit_view(request, pk):
    """
    HRM gửi phiếu lương cho Finance duyệt.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.payroll_submit")

    slip = payroll_submit_for_review(salary_slip_id=pk, user=user)
    out_serializer = SalarySlipOutputSerializer(slip)
    return Response(out_serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def salary_slip_bulk_calculate_view(request):
    """
    Tính toán hàng loạt phiếu lương.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.change_salaryslip")

    salary_period = request.data.get("salary_period")
    if not salary_period:
        raise ValidationException("Kỳ lương (salary_period) là bắt buộc")

    result = payroll_bulk_calculate(salary_period=salary_period, creator=user)
    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def salary_slip_bulk_submit_view(request):
    """
    HRM gửi hàng loạt phiếu lương cho Finance duyệt.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.payroll_submit")

    salary_period = request.data.get("salary_period")
    if not salary_period:
        raise ValidationException("Kỳ lương (salary_period) là bắt buộc")

    result = payroll_bulk_submit_for_review(salary_period=salary_period, user=user)
    return Response(result, status=status.HTTP_200_OK)
