from django.db import migrations


def add_hrm_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    hrm_permissions = [
        {"code": "hrm.view_employee", "name": "Xem Nhân Viên"},
        {"code": "hrm.add_employee", "name": "Thêm Nhân Viên"},
        {"code": "hrm.change_employee", "name": "Sửa Nhân Viên"},
        {"code": "hrm.add_employmentcontract", "name": "Thêm Hợp Đồng Lao Động"},
        {"code": "hrm.change_employmentcontract", "name": "Sửa Hợp Đồng Lao Động"},
        {"code": "hrm.view_attendance", "name": "Xem Chấm Công"},
        {"code": "hrm.add_attendance", "name": "Thêm Chấm Công"},
        {"code": "hrm.view_leaverequest", "name": "Xem Đơn Nghỉ Phép"},
        {"code": "hrm.add_leaverequest", "name": "Thêm Đơn Nghỉ Phép"},
        {"code": "hrm.change_leaverequest", "name": "Sửa Đơn Nghỉ Phép"},
        {"code": "hrm.add_rewardrecord", "name": "Thêm Khen Thưởng"},
        {"code": "hrm.add_disciplinerecord", "name": "Thêm Kỷ Luật"},
        {"code": "finance.view_salaryslip", "name": "Xem Phiếu Lương"},
        {"code": "finance.add_salaryslip", "name": "Thêm Phiếu Lương"},
        {"code": "finance.change_salaryslip", "name": "Sửa Phiếu Lương"},
    ]

    for perm_data in hrm_permissions:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_hrm_permissions(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_auto_20260521_0016"),
    ]

    operations = [
        migrations.RunPython(add_hrm_permissions_to_admin, remove_hrm_permissions),
    ]
