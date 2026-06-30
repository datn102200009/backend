import pytest

pytestmark = pytest.mark.django_db


def test_collect_invoice_renamed_to_collect_sales_invoice():
    from apps.accounts.models import Permission

    code = "finance.collect_sales_invoice"
    perm = Permission.objects.filter(code=code).first()
    assert perm is not None
    assert perm.name == "Thu tiền hóa đơn bán hàng"
    # Đảm bảo code cũ không tồn tại
    assert not Permission.objects.filter(code="finance.collect_invoice").exists()


def test_credit_bypass_renamed_to_finance_credit_bypass():
    from apps.accounts.models import Permission, User, UserPermission

    # Đảm bảo code mới tồn tại
    new_code = "finance.approve_credit_bypass"
    new_perm = Permission.objects.filter(code=new_code).first()
    assert new_perm is not None
    assert new_perm.name == "Phê duyệt tín dụng đặc cách (Finance)"

    # Đảm bảo code cũ không tồn tại
    assert not Permission.objects.filter(code="sales.approve_credit_bypass").exists()

    # Đảm bảo admin user có permission mới này
    admin_user = User.objects.filter(username="admin").first()
    if admin_user:
        assert UserPermission.objects.filter(user=admin_user, permission=new_perm).exists()
