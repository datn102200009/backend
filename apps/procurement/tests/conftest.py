from unittest.mock import patch

import pytest

from apps.common.tests.conftest import admin_user, api_client, mock_permission, regular_user


@pytest.fixture(autouse=True)
def mock_permission_checker():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as mock_check:
        yield mock_check
