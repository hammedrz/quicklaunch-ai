"""System tray manager for QuickLaunch AI running persistently in the background."""
from typing import Callable, Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import styles


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

        if self.on_clear_history:
            clear_hist_action = QAction("Clear Query History", self._menu)
            clear_hist_action.triggered.connect(self.on_clear_history)
            self._menu.addAction(clear_hist_action)

        self._menu.addSeparator()

        quit_action = QAction("Exit QuickLaunch AI", self._menu)
        quit_action.triggered.connect(self.on_quit)
        self._menu.addAction(quit_action)

        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_click)

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
