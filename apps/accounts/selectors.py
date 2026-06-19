from apps.accounts.models import Role, User
from apps.master_data.models import Employee


def role_list():
    """
    Trả về danh sách tất cả các vai trò (roles) trong hệ thống,
    sắp xếp theo tên vai trò.
    """
    return Role.objects.all().order_by("name")


def user_list(*, search: str = None):
    """
    Trả về danh sách tất cả tài khoản người dùng kèm theo vai trò
    và nạp trước các quyền được gán trực tiếp.
    """
    qs = User.objects.prefetch_related("direct_permissions__permission").all().order_by("-created_at")

    if search:
        qs = qs.filter(username__icontains=search)

    return qs


def unlinked_employees_list():
    """
    Trả về danh sách các nhân viên đang hoạt động nhưng chưa được tạo tài khoản User.
    """
    # Lấy danh sách employee_id đã được liên kết với User
    linked_employee_ids = (
        User.objects.exclude(employee_id__isnull=True).exclude(employee_id="").values_list("employee_id", flat=True)
    )

    # Lấy các nhân viên đang hoạt động và không nằm trong danh sách đã liên kết
    return (
        Employee.objects.filter(employment_status="active")
        .exclude(employee_id__in=linked_employee_ids)
        .order_by("employee_id")
    )
