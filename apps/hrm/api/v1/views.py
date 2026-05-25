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
    ContractCreateOrRenewInputSerializer,
    ContractTerminateInputSerializer,
    DisciplineRecordCreateInputSerializer,
    DisciplineRecordOutputSerializer,
    EmployeeCreateInputSerializer,
    EmployeeDetailOutputSerializer,
    EmployeeOutputSerializer,
    EmployeeUpdateInputSerializer,
    EmployeeUpdateSalaryTitleInputSerializer,
    EmploymentContractOutputSerializer,
    LeaveRequestApproveInputSerializer,
    LeaveRequestCreateInputSerializer,
    LeaveRequestOutputSerializer,
    RewardRecordCreateInputSerializer,
    RewardRecordOutputSerializer,
    SalarySlipBulkConfirmInputSerializer,
    SalarySlipConfirmInputSerializer,
    SalarySlipInitializeInputSerializer,
    SalarySlipOutputSerializer,
)
from apps.hrm.models import Attendance, DisciplineRecord, EmploymentContract, LeaveRequest, RewardRecord
from apps.hrm.selectors import employee_get_detail_with_relations
from apps.hrm.services import (
    attendance_batch_record,
    contract_create_or_renew,
    contract_terminate,
    discipline_record_create,
    employee_create_with_user,
    employee_update,
    employee_update_salary_or_title,
    leave_request_approve,
    leave_request_create,
    payroll_bulk_confirm_and_pay,
    payroll_calculate_salary,
    payroll_confirm_and_pay,
    payroll_initialize_period,
    reward_record_create,
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
    Tạo mới một nhân viên (và tài khoản người dùng nếu được yêu cầu).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.add_employee")

    serializer = EmployeeCreateInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        employee = employee_create_with_user(
            data=serializer.validated_data,
            creator=user,
        )
    except IntegrityError:
        raise ValidationException("Dữ liệu bị trùng lặp hoặc vi phạm ràng buộc CSDL. Vui lòng kiểm tra lại.")

    out_serializer = EmployeeOutputSerializer(employee)
    return Response(out_serializer.data, status=status.HTTP_201_CREATED)


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
def employee_update_salary_title_view(request, pk):
    """
    Điều chỉnh lương cơ bản, chức danh, hoặc phòng ban của nhân viên (tự động lưu lịch sử).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.change_employee")

    serializer = EmployeeUpdateSalaryTitleInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    updated_employee = employee_update_salary_or_title(
        employee_id=pk,
        change_data=serializer.validated_data,
        approved_by_user_id=str(user.id),
        approved_by=user,
    )

    out_serializer = EmployeeOutputSerializer(updated_employee)
    return Response(out_serializer.data, status=status.HTTP_200_OK)


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
    Hỗ trợ lọc theo date và employee_id.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.view_attendance")

    date_param = request.query_params.get("date")
    employee_id = request.query_params.get("employee_id")

    qs = Attendance.objects.all().select_related("employee").order_by("-date", "employee__employee_id")

    if date_param:
        qs = qs.filter(date=date_param)
    if employee_id:
        qs = qs.filter(employee_id=employee_id)

    serializer = AttendanceOutputSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


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
    Lọc theo status và employee_id.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "hrm.view_leaverequest")

    status_param = request.query_params.get("status")
    employee_id = request.query_params.get("employee_id")

    qs = LeaveRequest.objects.all().select_related("employee", "approved_by").order_by("-created_at")

    if status_param:
        qs = qs.filter(status=status_param)
    if employee_id:
        qs = qs.filter(employee_id=employee_id)

    serializer = LeaveRequestOutputSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


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

    # Cố định số ngày công tiêu chuẩn là 26 ngày
    standard_days = 26

    updated_slip = payroll_calculate_salary(
        salary_slip_id=pk,
        standard_days=standard_days,
        creator=user,
    )

    out_serializer = SalarySlipOutputSerializer(updated_slip)
    return Response(out_serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def salary_slip_confirm_view(request, pk):
    """
    Xác nhận chi trả lương và tự động ghi nhận bút toán CashFlowTransaction.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.change_salaryslip")

    try:
        slip = SalarySlip.objects.get(id=pk)
    except SalarySlip.DoesNotExist:
        raise NotFoundException("Không tìm thấy phiếu lương")

    serializer = SalarySlipConfirmInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    payment_method = serializer.validated_data["payment_method"]

    # Lưu payment_method trước khi confirm
    old_method = slip.payment_method
    if old_method != payment_method:
        slip.payment_method = payment_method
        slip.save(update_fields=["payment_method"])
        create_system_log(
            user=user,
            action="update",
            table_name="salary_slip",
            record_id=str(slip.id),
            old_value={"payment_method": old_method},
            new_value={"payment_method": payment_method},
        )

    # Chạy confirm & pay
    updated_slip = payroll_confirm_and_pay(
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
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_rewardrecord")
        employee_id = request.query_params.get("employee_id")
        qs = RewardRecord.objects.all().select_related("employee").order_by("-reward_date")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        serializer = RewardRecordOutputSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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


@api_view(["GET", "POST"])
@throttle_classes([UserRateThrottle])
def discipline_list_create_view(request):
    """
    Xem danh sách hoặc ghi nhận kỷ luật của nhân viên.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == "GET":
        PermissionChecker.check_permission(user, "hrm.view_disciplinerecord")
        employee_id = request.query_params.get("employee_id")
        qs = DisciplineRecord.objects.all().select_related("employee").order_by("-discipline_date")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        serializer = DisciplineRecordOutputSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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


@api_view(["POST"])
@throttle_classes([UserRateThrottle])
def salary_slip_bulk_confirm_view(request):
    """
    Xác nhận chi trả lương nhanh cho toàn bộ phiếu lương chưa thanh toán của kỳ lương.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({"error": "User không được xác thực"}, status=status.HTTP_401_UNAUTHORIZED)

    PermissionChecker.check_permission(user, "finance.change_salaryslip")

    serializer = SalarySlipBulkConfirmInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    salary_period = serializer.validated_data["salary_period"]
    payment_method = serializer.validated_data["payment_method"]

    updated_slips = payroll_bulk_confirm_and_pay(
        salary_period=salary_period,
        payment_method=payment_method,
        creator=user,
    )

    out_serializer = SalarySlipOutputSerializer(updated_slips, many=True)
    return Response(out_serializer.data, status=status.HTTP_200_OK)
