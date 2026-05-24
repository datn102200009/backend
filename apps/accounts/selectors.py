from apps.accounts.models import Role


def role_list():
    """
    Trả về danh sách tất cả các vai trò (roles) trong hệ thống,
    sắp xếp theo tên vai trò.
    """
    return Role.objects.all().order_by("name")
