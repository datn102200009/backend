import os

service_files = [
    "apps/purchasing/tests/test_services_order.py",
    "apps/purchasing/tests/test_services_invoice.py",
    "apps/sales/tests/test_services_order.py",
    "apps/sales/tests/test_services_invoice.py",
    "apps/finance/tests/test_services_cash_flow.py",
]

for f in service_files:
    with open(f, "r", encoding="utf-8") as file:
        lines = file.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith('@patch("apps.common.xlib.permissions.'):
            continue
        if ", mock_permission):" in line:
            new_lines.append(line.replace(", mock_permission):", "):"))
        else:
            new_lines.append(line)

    with open(f, "w", encoding="utf-8") as file:
        file.writelines(new_lines)
    print(f"Cleaned {f}")

conftest_content = """import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_permission_checker():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as mock_check:
        yield mock_check
"""

for app in ["purchasing", "sales", "finance"]:
    conftest_path = f"apps/{app}/tests/conftest.py"
    with open(conftest_path, "w", encoding="utf-8") as file:
        file.write(conftest_content)
    print(f"Created {conftest_path}")
