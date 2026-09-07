"""Main launcher window: frameless, floating, Raycast-style AI bar with 3-mode support."""
import sys
from typing import Optional

from PySide6.QtCore import (
    QPoint,
    QRect,
    QTimer,
    Qt,
)
from PySide6.QtGui import QColor, QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QVBoxLayout,
    QWidget,
)

from ..config import config
from ..state_manager import state_manager
from ..worker import AgentWorker
from . import styles
from .api_key_dialog import ApiKeyDialog
from .drag_handle import DragHandle
from .result_view import ResultView
from .search_bar import SearchBar
from .status_bar import StatusBar
from .thought_view import ThoughtView


class LauncherWindow(QWidget):
    """Frameless floating Raycast-style launcher window with persistent state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LauncherRoot")
        self.setWindowTitle("QuickLaunch AI")

        # Window flags: frameless, always on top, tool window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 140))

        # Inner container
        self._container = QWidget(self)
        self._container.setObjectName("LauncherContainer")
        self._container.setStyleSheet(styles.WINDOW_STYLE)
        self._container.setGraphicsEffect(shadow)

        # Main layout inside container
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Drag handle
        self.drag_handle = DragHandle(self._container)
        self._main_layout.addWidget(self.drag_handle)

        # Search bar
        self.search_bar = SearchBar(self._container)
        self.search_bar.prompt_submitted.connect(self._on_submit)
        self.search_bar.mode_changed.connect(self._on_mode_changed)
        self.search_bar.model_changed.connect(self._on_model_changed)
        self._main_layout.addWidget(self.search_bar)

        # Thought view
        self.thought_view = ThoughtView(self._container)
        self.thought_view.expansion_changed.connect(self._adjust_window_size)
        self._main_layout.addWidget(self.thought_view)

        # Result view
        self.result_view = ResultView(self._container)
        self.result_view.content_resized.connect(self._adjust_window_size)
        self._main_layout.addWidget(self.result_view, stretch=1)

        # Status bar
        self.status_bar = StatusBar(self._container)
        self._main_layout.addWidget(self.status_bar)

        # Outer layout for drop shadow margins (contained strictly within window bounds)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 20, 24, 20)
        outer_layout.addWidget(self._container)

        # Debounced resize timer to prevent 60 HWND resizes per second
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(40)
        self._resize_timer.timeout.connect(self._do_adjust_window_size)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.dismiss)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._clear_all)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._smart_copy)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(
            self.search_bar.mode_pill.toggle
        )
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(
            self.search_bar.model_selector.show_menu
        )
        QShortcut(QKeySequence("Ctrl+Shift+R"), self).activated.connect(self.recenter)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self.open_settings)

        # Drag & positioning state
        self._drag_pos: Optional[QPoint] = None
        self._user_moved = False
        self._worker: Optional[AgentWorker] = None

        # Sizing
        self.setFixedWidth(config.window_width)
        self._reset_collapsed_height()

        # Load persistent state
        saved_pos, user_moved, saved_mode = state_manager.load_window_state()
        self._user_moved = False
        self._saved_mode = saved_mode

        if saved_pos and user_moved:
            self.move(saved_pos)
        else:
            self._position_on_screen()

        # Set loaded mode
        self.search_bar.set_mode(saved_mode)
        self.status_bar.set_mode(saved_mode)

    def paintEvent(self, event):
        pass  # Transparent root window

    def _base_collapsed_height(self) -> int:
        return (
            styles.DRAG_HANDLE_HEIGHT
            + styles.INPUT_HEIGHT + 10
            + styles.STATUS_BAR_HEIGHT
            + 40  # outer margins (20 top + 20 bottom)
        )

    def _reset_collapsed_height(self):
        """Resets height constraints so window can fully collapse."""
        h = self._base_collapsed_height()
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        self.resize(self.width(), h)

    def _get_active_screen(self):
        """Returns the screen containing the mouse cursor, falling back to primaryScreen."""
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos)
        return screen or QApplication.primaryScreen()

    def _position_on_screen(self):
        """Centers the launcher in the upper-third of the active monitor."""
        screen = self._get_active_screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + int(geo.height() * 0.18)
            self.move(x, y)

    def _ensure_on_screen(self):
        """Ensures the window is visible on an active monitor if previously moved."""
        current_geo = self.geometry()
        handle_rect = QRect(current_geo.x() + 50, current_geo.y(), max(current_geo.width() - 100, 50), 50)
        is_visible = False
        for screen in QApplication.screens():
            if screen.availableGeometry().intersects(handle_rect):
                is_visible = True
                break
        if not is_visible:
            self.recenter()

    def recenter(self):
        """Re-centers the launcher window and resets saved state."""
        self._user_moved = False
        self._position_on_screen()
        state_manager.save_window_state(
            pos=self.pos(),
            user_moved=False,
            mode=self.search_bar.current_mode,
        )

    def summon(self):
        """Shows and brings the launcher into foreground focus on Windows."""
        if not self._user_moved:
            self._position_on_screen()
        else:
            self._ensure_on_screen()

        self.show()
        self.raise_()
        self.activateWindow()

        # Native Win32 foreground activation for Windows 10/11
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.ShowWindow(hwnd, 5)  # SW_SHOW

                # AttachThreadInput ensures foreground activation even when another application has focus lock
                fg_hwnd = user32.GetForegroundWindow()
                if fg_hwnd:
                    fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
                    cur_tid = kernel32.GetCurrentThreadId()
                    if fg_tid and fg_tid != cur_tid:
                        user32.AttachThreadInput(cur_tid, fg_tid, True)
                        user32.SetForegroundWindow(hwnd)
                        user32.AttachThreadInput(cur_tid, fg_tid, False)
                    else:
                        user32.SetForegroundWindow(hwnd)
                else:
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        self.search_bar.focus_input()

    def dismiss(self):
        """Hides launcher and cleanly recovers worker state."""
        self._drag_pos = None
        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self.search_bar.set_loading(False)
        self.hide()

    def hideEvent(self, event):
        self._drag_pos = None
        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()
        super().hideEvent(event)

    # ── Mouse Drag & Move ─────────────────────────────────────────────
    def _is_drag_target(self, pos: QPoint) -> bool:
        """Only DragHandle and StatusBar initiate window drags."""
        global_press = self.mapToGlobal(pos)
        if self.drag_handle.rect().contains(self.drag_handle.mapFromGlobal(global_press)):
            return True
        if self.status_bar.rect().contains(self.status_bar.mapFromGlobal(global_press)):
            return True
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_drag_target(event.position().toPoint()):
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._user_moved = True
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()
        state_manager.save_window_state(
            pos=self.pos(),
            user_moved=self._user_moved,
            mode=self.search_bar.current_mode,
        )
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_drag_target(event.position().toPoint()):
            self.recenter()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    # ── Mode ──────────────────────────────────────────────────────────
    def _on_mode_changed(self, mode: str):
        self.status_bar.set_mode(mode)
        state_manager.save_window_state(
            pos=self.pos(),
            user_moved=self._user_moved,
            mode=mode,
        )

    def _on_model_changed(self, mode: str, model: str):
        state_manager.save_window_state(
            pos=self.pos(),
            user_moved=self._user_moved,
            mode=self.search_bar.current_mode,
        )

    # ── Submit & Execute ──────────────────────────────────────────────
    def _on_submit(self, prompt: str):
        # Intercept missing API key for Simple & Agent modes
        mode = self.search_bar.current_mode
        if mode in ("simple", "agent") and not config.is_api_key_configured():
            self.result_view.clear()
            self.result_view.set_status("⚠️ API Key Required")
            self.result_view.append_chunk(
                "### 🔑 Gemini API Key Not Configured\n\n"
                "Please configure your Google Gemini API key to use Simple and Agent modes.\n\n"
                "Press **Ctrl+,** or use the settings dialog."
            )
            self.result_view.finalize_markdown()
            self._adjust_window_size()
            self.open_settings()
            return

        # If a worker is running, cancel it
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(150)

        # Clear previous results
        self.result_view.clear()
        self.thought_view.clear()

        self.search_bar.set_loading(True)

        worker = AgentWorker(prompt=prompt, mode=mode, parent=self)
        self._worker = worker
        worker.sig_chunk.connect(self._on_chunk)
        worker.sig_thought.connect(self._on_thought)
        worker.sig_status.connect(self._on_status)
        worker.sig_sources.connect(self._on_sources)
        worker.sig_tool_activity.connect(self._on_tool_activity)
        worker.sig_finished.connect(self._on_finished)
        worker.sig_error.connect(self._on_error)
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    def _on_chunk(self, chunk: str):
        self.result_view.append_chunk(chunk)
        self._adjust_window_size()

    def _on_thought(self, thought: str):
        self.thought_view.append_thought(thought)
        self._adjust_window_size()

    def _on_status(self, status: str):
        self.result_view.set_status(status)
        self._adjust_window_size()

    def _on_sources(self, sources: list):
        self.result_view.set_sources(sources)
        self._adjust_window_size()

    def _on_tool_activity(self, name: str, args: dict):
        self.result_view.set_status(f"⚙️ Running {name}...")
        self._adjust_window_size()

    def _on_finished(self, full_text: str):
        self.search_bar.set_loading(False)
        self.thought_view.set_finished()
        self.result_view.finalize_markdown()
        self.result_view.set_status("")
        self._do_adjust_window_size()

    def _on_error(self, error: str):
        self.search_bar.set_loading(False)
        self.thought_view.set_finished()
        self.result_view.clear()
        self.result_view.set_status("⚠️ Request Issue")
        self.result_view.append_chunk(f"### ⚠️ Error\n\n{error}")
        self.result_view.finalize_markdown()
        self._do_adjust_window_size()

    def _on_worker_finished(self):
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _adjust_window_size(self):
        """Schedules debounced window sizing."""
        if not self._resize_timer.isActive():
            self._resize_timer.start()

    def _do_adjust_window_size(self):
        """Dynamically adjusts window height based on container content."""
        desired = self._container.sizeHint().height() + 40
        min_h = self._base_collapsed_height()

        screen = self._get_active_screen()
        screen_max = int(screen.availableGeometry().height() * 0.85) if screen else 780
        max_h = min(max(config.max_window_height, 760), screen_max)
        new_h = min(max(desired, min_h), max_h)

        self.setMinimumHeight(min_h)
        self.setMaximumHeight(max_h)

        if abs(new_h - self.height()) > 2:
            self.resize(self.width(), new_h)

    # ── Actions & Settings ────────────────────────────────────────────
    def open_settings(self):
        """Opens the API key configuration dialog."""
        dlg = ApiKeyDialog(self)
        dlg.exec()

    def _clear_all(self):
        """Resets search bar, result views, and collapses window height."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self.search_bar.clear_input()
        self.result_view.clear()
        self.thought_view.clear()
        self.search_bar.set_loading(False)
        self._reset_collapsed_height()
        self.search_bar.focus_input()

    def _smart_copy(self):
        """Selection-aware copy: copies selected text, or full result if none selected."""
        # 1. Check prompt input selection
        if self.search_bar.input.hasSelectedText():
            QApplication.clipboard().setText(self.search_bar.input.selectedText())
            return

        # 2. Check result view selection
        selected = self.result_view.get_selected_text()
        if selected:
            QApplication.clipboard().setText(selected)
            return

        # 3. Fallback: Copy entire result text
        text = self.result_view.get_text()
        if text:
            QApplication.clipboard().setText(text)
            self.result_view.set_status("✅ Copied result to clipboard!")
            QTimer.singleShot(2000, lambda: self.result_view.set_status(""))
