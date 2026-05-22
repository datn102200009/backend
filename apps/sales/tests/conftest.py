from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_permission_checker():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as mock_check:
        yield mock_check
