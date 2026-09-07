"""Tests for centralized logger setup and tray log integration."""
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from src.logger import get_log_file_path, setup_logging


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_get_log_file_path():
    p = get_log_file_path()
    assert isinstance(p, Path)
    assert p.name == "quicklaunch.log"


def test_setup_logging_creates_file(tmp_path):
    with patch("src.logger.get_log_file_path", return_value=tmp_path / "quicklaunch.log"):
        import src.logger as logger_module
        logger_module._logging_initialized = False

        log_path = setup_logging("DEBUG")
        assert log_path == tmp_path / "quicklaunch.log"

        test_logger = logging.getLogger("TestModule")
        test_logger.info("Test log message for hotkey diagnostics")

        # Flush handlers
        for handler in logging.getLogger().handlers:
            handler.flush()

        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "Test log message for hotkey diagnostics" in content
        assert "[INFO   ]" in content or "[INFO]" in content


def test_tray_view_logs_action(qapp):
    from src.ui.tray import SystemTrayManager
    mock_show = MagicMock()
    mock_toggle = MagicMock()
    mock_clear = MagicMock()
    mock_quit = MagicMock()

    tray = SystemTrayManager(
        on_show=mock_show,
        on_toggle_mode=mock_toggle,
        on_clear=mock_clear,
        on_quit=mock_quit,
        hotkey_str="ctrl+space",
    )

    # Check menu has View Logs action
    actions = [action.text() for action in tray._menu.actions()]
    assert any("View Logs" in action_text for action_text in actions)
