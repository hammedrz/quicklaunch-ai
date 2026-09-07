"""System tray manager for QuickLaunch AI running persistently in the background."""
import logging
import os
import sys
from typing import Callable, Optional

logger = logging.getLogger("QuickLaunch.Tray")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import styles
from ..autostart import is_autostart_enabled, toggle_autostart


def create_tray_icon() -> QIcon:
    """Renders multi-resolution tray icons for crisp display across all DPI scales."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background circle
        painter.setBrush(QBrush(QColor("#0a84ff")))
        painter.setPen(Qt.PenStyle.NoPen)
        margin = size * 0.06
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)

        # Scaled lightning bolt
        scale = size / 32.0
        bolt = QPolygonF([
            QPointF(18 * scale, 4 * scale),
            QPointF(10 * scale, 16 * scale),
            QPointF(15 * scale, 16 * scale),
            QPointF(14 * scale, 28 * scale),
            QPointF(22 * scale, 14 * scale),
            QPointF(17 * scale, 14 * scale),
        ])
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawPolygon(bolt)
        painter.end()

        icon.addPixmap(pixmap)
    return icon


class SystemTrayManager:
    """Manages the Windows System Tray icon, context menu, and notifications."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_toggle_mode: Callable[[], None],
        on_clear: Callable[[], None],
        on_quit: Callable[[], None],
        on_recenter: Optional[Callable[[], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_clear_history: Optional[Callable[[], None]] = None,
        hotkey_str: str = "Alt+Space",
        parent=None,
    ):
        self.on_show = on_show
        self.on_toggle_mode = on_toggle_mode
        self.on_clear = on_clear
        self.on_quit = on_quit
        self.on_recenter = on_recenter
        self.on_settings = on_settings
        self.on_clear_history = on_clear_history
        self._hotkey_str = hotkey_str

        self._tray = QSystemTrayIcon(parent)
        self.update_tooltip(hotkey_str)
        self._tray.setIcon(create_tray_icon())

        # Context menu
        self._menu = QMenu(parent)
        self._menu.setStyleSheet(styles.MENU_STYLE)

        self._open_action = QAction(self._get_open_label(hotkey_str), self._menu)
        self._open_action.triggered.connect(self.on_show)
        self._menu.addAction(self._open_action)

        if self.on_recenter:
            recenter_action = QAction("Center Window", self._menu)
            recenter_action.triggered.connect(self.on_recenter)
            self._menu.addAction(recenter_action)

        self._menu.addSeparator()

        mode_action = QAction("Switch Mode (Tab)", self._menu)
        mode_action.triggered.connect(self.on_toggle_mode)
        self._menu.addAction(mode_action)

        clear_action = QAction("Clear Session (Ctrl+L)", self._menu)
        clear_action.triggered.connect(self.on_clear)
        self._menu.addAction(clear_action)

        if self.on_settings:
            settings_action = QAction("Configure API Key... (Ctrl+,)", self._menu)
            settings_action.triggered.connect(self.on_settings)
            self._menu.addAction(settings_action)

        # Startup registration toggle
        self._autostart_action = QAction("Run at Startup", self._menu)
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(is_autostart_enabled())
        self._autostart_action.triggered.connect(self._on_autostart_toggled)
        self._menu.addAction(self._autostart_action)

        if self.on_clear_history:
            clear_hist_action = QAction("Clear Query History", self._menu)
            clear_hist_action.triggered.connect(self.on_clear_history)
            self._menu.addAction(clear_hist_action)

        self._menu.addSeparator()

        logs_action = QAction("View Logs (quicklaunch.log)", self._menu)
        logs_action.triggered.connect(self._open_log_file)
        self._menu.addAction(logs_action)

        quit_action = QAction("Exit QuickLaunch AI", self._menu)
        quit_action.triggered.connect(self.on_quit)
        self._menu.addAction(quit_action)

        self._menu.aboutToShow.connect(self._sync_autostart_state)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_click)

    def _sync_autostart_state(self):
        """Synchronizes checkbox with actual OS/Task Manager state when menu opens."""
        self._autostart_action.setChecked(is_autostart_enabled())

    def _on_autostart_toggled(self, checked: bool):
        """Handles user toggling the 'Run at Startup' menu option."""
        success, msg = toggle_autostart(checked)
        if success:
            logger.info("Startup status updated: %s", msg)
        else:
            logger.warning("Failed to update startup status: %s", msg)
            self._autostart_action.setChecked(not checked)
            self.show_notification(
                "Startup Configuration",
                f"Could not update startup status: {msg}",
                is_warning=True,
            )

    def _open_log_file(self):
        """Opens the persistent application log file in the default system viewer."""
        try:
            from ..logger import get_log_file_path
            log_path = get_log_file_path()
            if log_path.exists():
                logger.info("Opening log file in default application: %s", log_path)
                if sys.platform == "win32":
                    os.startfile(str(log_path))
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", str(log_path)])
            else:
                self.show_notification(
                    "QuickLaunch AI Logs",
                    f"Log file not yet created at:\n{log_path}",
                    is_warning=True,
                )
        except Exception as err:
            logger.error("Failed to open log file: %s", err)

    def _get_open_label(self, hotkey: Optional[str]) -> str:
        if hotkey:
            formatted = hotkey.replace("+", " + ").title()
            return f"Open Launcher ({formatted})"
        return "Open Launcher"

    def update_hotkey(self, hotkey_str: Optional[str]):
        """Dynamically updates the open action label and tooltip when hotkeys change."""
        self._hotkey_str = hotkey_str or ""
        self._open_action.setText(self._get_open_label(hotkey_str))
        self.update_tooltip(hotkey_str)

    def update_tooltip(self, hotkey_str: Optional[str]):
        if hotkey_str:
            formatted = hotkey_str.replace("+", " + ").title()
            self._tray.setToolTip(f"QuickLaunch AI ({formatted})")
        else:
            self._tray.setToolTip("QuickLaunch AI (No Hotkey)")

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()

    def cleanup(self):
        """Explicitly deletes the shell notification icon on exit to avoid ghost icons."""
        self._tray.hide()
        self._tray.setParent(None)

    def show_notification(self, title: str, msg: str, is_warning: bool = False):
        icon = (
            QSystemTrayIcon.MessageIcon.Warning
            if is_warning
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._tray.showMessage(title, msg, icon, 3000)

    def _on_tray_click(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.on_show()
