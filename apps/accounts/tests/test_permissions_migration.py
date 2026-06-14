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
