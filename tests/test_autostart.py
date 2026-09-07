"""Unit tests for Windows Startup Apps manager (src/autostart.py)."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.autostart import (
    APP_NAME,
    SHORTCUT_FILENAME,
    disable_autostart,
    enable_autostart,
    get_shortcut_path,
    get_startup_folder,
    is_autostart_enabled,
    is_windows,
    toggle_autostart,
)


def test_app_name_and_filename():
    assert APP_NAME == "QuickLaunch AI"
    assert SHORTCUT_FILENAME == "QuickLaunch AI.lnk"


def test_is_windows():
    assert is_windows() == (sys.platform == "win32")


def test_get_startup_folder():
    folder = get_startup_folder()
    assert isinstance(folder, Path)
    assert "Startup" in folder.parts
    assert "Start Menu" in folder.parts


def test_get_shortcut_path():
    shortcut = get_shortcut_path()
    assert shortcut.name == "QuickLaunch AI.lnk"
    assert shortcut.parent == get_startup_folder()


def test_is_autostart_enabled_when_shortcut_missing(tmp_path):
    fake_shortcut = tmp_path / "QuickLaunch AI.lnk"
    with patch("src.autostart.get_shortcut_path", return_value=fake_shortcut), \
         patch("src.autostart.is_windows", return_value=True):
        assert is_autostart_enabled() is False


def test_is_autostart_enabled_when_shortcut_exists_no_registry_block(tmp_path):
    fake_shortcut = tmp_path / "QuickLaunch AI.lnk"
    fake_shortcut.touch()
    with patch("src.autostart.get_shortcut_path", return_value=fake_shortcut), \
         patch("src.autostart.is_windows", return_value=True):
        if sys.platform == "win32":
            # If winreg is available, mock query to FileNotFoundError (meaning default enabled)
            with patch("winreg.OpenKey", side_effect=FileNotFoundError):
                assert is_autostart_enabled() is True
        else:
            assert is_autostart_enabled() is True


def test_is_autostart_enabled_when_disabled_in_task_manager(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows registry test")

    import winreg

    fake_shortcut = tmp_path / "QuickLaunch AI.lnk"
    fake_shortcut.touch()

    # Binary flag with 0x03 as first byte = disabled in Task Manager
    mock_reg_value = (b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00", winreg.REG_BINARY)

    mock_key = MagicMock()
    with patch("src.autostart.get_shortcut_path", return_value=fake_shortcut), \
         patch("src.autostart.is_windows", return_value=True), \
         patch("winreg.OpenKey", return_value=mock_key), \
         patch("winreg.QueryValueEx", return_value=mock_reg_value):
        assert is_autostart_enabled() is False


def test_disable_autostart(tmp_path):
    fake_shortcut = tmp_path / "QuickLaunch AI.lnk"
    fake_shortcut.touch()
    assert fake_shortcut.exists()

    with patch("src.autostart.get_shortcut_path", return_value=fake_shortcut):
        success, msg = disable_autostart()
        assert success is True
        assert msg == "Disabled"
        assert not fake_shortcut.exists()


def test_disable_autostart_when_already_missing(tmp_path):
    fake_shortcut = tmp_path / "QuickLaunch AI.lnk"
    assert not fake_shortcut.exists()

    with patch("src.autostart.get_shortcut_path", return_value=fake_shortcut):
        success, msg = disable_autostart()
        assert success is True
        assert msg == "Disabled"


def test_toggle_autostart():
    with patch("src.autostart.enable_autostart", return_value=(True, "Enabled")) as mock_enable, \
         patch("src.autostart.disable_autostart", return_value=(True, "Disabled")) as mock_disable:
        toggle_autostart(True)
        mock_enable.assert_called_once()
        mock_disable.assert_not_called()

        toggle_autostart(False)
        mock_disable.assert_called_once()
