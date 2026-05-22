import os


def fix_file(filepath, replacements):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    for old, new in replacements.items():
        content = content.replace(old, new)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Fixed {filepath}")


# 1. Fix test_models.py
fix_file(
    "apps/purchasing/tests/test_models.py",
    {'startswith("PO-")': 'startswith("Purchase Order")', 'startswith("PINV-")': 'startswith("Purchase Invoice")'},
)

fix_file(
    "apps/sales/tests/test_models.py",
    {'startswith("SO-")': 'startswith("Sales Order")', 'startswith("SINV-")': 'startswith("Sales Invoice")'},
)

# 2. Fix test_services*.py
service_files = [
    "apps/purchasing/tests/test_services_order.py",
    "apps/purchasing/tests/test_services_invoice.py",
    "apps/sales/tests/test_services_order.py",
    "apps/sales/tests/test_services_invoice.py",
    "apps/finance/tests/test_services_cash_flow.py",
]

patch_import = "from unittest.mock import patch\n"
patch_decorator = '    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")\n'

for f in service_files:
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()

    if "from unittest.mock import patch" not in content:
        content = patch_import + content

    # Replace def test_ with @patch and def test_
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        if line.strip().startswith("def test_"):
            new_lines.append('    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")')
            # Thêm mock_permission argument
            new_line = line.replace("):", ", mock_permission):")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    with open(f, "w", encoding="utf-8") as file:
        file.write("\n".join(new_lines))
    print(f"Fixed {f}")
