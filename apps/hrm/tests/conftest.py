"""Test configuration for hrm app."""

from unittest.mock import patch

import pytest

from apps.common.tests.conftest import admin_user, api_client, mock_permission, regular_user


@pytest.fixture(autouse=True)
def mock_check_permission():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as mock:
        mock.return_value = True
        yield mock
