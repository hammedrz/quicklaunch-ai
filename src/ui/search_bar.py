"""Search bar widget: prompt input with 3-mode pill, model selector, query history navigation, and loading spinner."""
from typing import List
from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QWidget,
)

from ..ai.model_registry import model_registry
from ..config import config
from ..state_manager import state_manager
from . import styles


class ModePill(QPushButton):
    """Clickable 3-mode toggle badge: [⚡ Simple] ↔ [🤖 Agent] ↔ [🚀 CLI]."""

    mode_toggled = Signal(str)

    MODES = ["simple", "agent", "cli"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModePill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mode = "simple"
        self._update_display()
        self.clicked.connect(self.toggle)

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        cleaned = mode.lower()
        if cleaned in self.MODES and cleaned != self._mode:
            self._mode = cleaned
            self._update_display()

    def toggle(self):
        idx = self.MODES.index(self._mode) if self._mode in self.MODES else 0
        self._mode = self.MODES[(idx + 1) % len(self.MODES)]
        self._update_display()
        self.mode_toggled.emit(self._mode)

    def _update_display(self):
        if self._mode == "simple":
            self.setText("⚡ Simple")
            self.setStyleSheet(styles.MODE_PILL_STYLE_SIMPLE)
            self.setToolTip("Simple Mode – Fast reasoning & tools (Tab to switch)")
        elif self._mode == "agent":
            self.setText("🤖 Agent")
            self.setStyleSheet(styles.MODE_PILL_STYLE_AGENT)
            self.setToolTip("Antigravity Agent Mode – Autonomous agent with reasoning stream (Tab to switch)")
        elif self._mode == "cli":
            self.setText("🚀 CLI")
            self.setStyleSheet(styles.MODE_PILL_STYLE_CLI)
            self.setToolTip("AGY CLI Mode – Runs via Antigravity CLI ('agy') engine (Tab to switch)")


class ModelSelector(QPushButton):
    """Clickable model badge showing the active model with a dynamically populated pop-up menu."""

    model_changed = Signal(str, str)  # (mode, model_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelSelector")
        self.setStyleSheet(styles.MODEL_SELECTOR_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mode = "simple"
        self._update_label()
        self.clicked.connect(self.show_menu)
        model_registry.models_updated.connect(self._on_models_updated)

    def _on_models_updated(self):
        self._update_label()

    def set_mode(self, mode: str):
        self._mode = mode.lower()
        self._update_label()

    def _get_active_model(self) -> str:
        if self._mode == "agent":
            return config.agent_model or "gemini-2.5-flash"
        elif self._mode == "cli":
            return config.cli_model or "default"
        else:
            return config.simple_model or "gemini-2.5-flash"

    def _update_label(self):
        active = self._get_active_model()
        if active == "default" or not active:
            display = "default"
        elif active.startswith("gemma"):
            display = active.replace("-it", "")
        else:
            display = active.replace("gemini-", "")
        self.setText(f"{display} ▾")
        self.setToolTip(f"Active Model: {active or 'default'}\nClick or press Ctrl+P to change model")

    def show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(styles.MENU_STYLE)

        models = model_registry.get_models(self._mode)
        current = self._get_active_model()

        for model_id, label in models:
            action = menu.addAction(label)
            is_active = (model_id == current) or (model_id == "" and current == "default")
            action.setCheckable(True)
            action.setChecked(is_active)
            action.triggered.connect(lambda checked=False, m=model_id: self._select_model(m))

        menu.addSeparator()
        refresh_action = menu.addAction("🔄 Refresh Models from API...")
        refresh_action.triggered.connect(self._on_refresh_triggered)

        menu.exec(self.mapToGlobal(QPoint(0, self.height() + 4)))

    def _on_refresh_triggered(self):
        self.setText("Refreshing... ▾")
        model_registry.refresh_async()

    def _select_model(self, model_id: str):
        if self._mode == "agent":
            config.agent_model = model_id or "gemini-2.5-flash"
        elif self._mode == "cli":
            config.cli_model = model_id
        else:
            config.simple_model = model_id or "gemini-2.5-flash"

        self._update_label()
        self.model_changed.emit(self._mode, model_id)



class SpinnerLabel(QLabel):
    """Minimal animated status indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Spinner")
        self.setStyleSheet(styles.SPINNER_STYLE)
        self.setFixedSize(QSize(20, 20))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()
        self._frames = ["◐", "◓", "◑", "◒"]
        self._idx = 0
        self._timer_id = None

    def start(self):
        self._idx = 0
        self.setText(self._frames[0])
        self.show()
        if self._timer_id is None:
            self._timer_id = self.startTimer(120)

    def stop(self):
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
        self.hide()

    def timerEvent(self, event):
        self._idx = (self._idx + 1) % len(self._frames)
        self.setText(self._frames[self._idx])


class PromptInput(QLineEdit):
    """Custom line edit supporting Enter submit, Tab mode switch, and Up/Down query history."""

    submit_requested = Signal(str)
    tab_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PromptInput")
        self.setStyleSheet(styles.INPUT_STYLE)
        self.setPlaceholderText("Ask anything or enter a command...")
        self.setFont(QFont("Segoe UI", 15))
        self.setMinimumHeight(styles.INPUT_HEIGHT)
        self.setClearButtonEnabled(True)

        # Query history state
        self._history: List[str] = state_manager.load_history()
        self._history_idx = -1
        self._draft_text = ""

        self.returnPressed.connect(self._on_return)

    def _on_return(self):
        text = self.text().strip()
        if text:
            self._history = state_manager.add_history(text)
            self._history_idx = -1
            self._draft_text = ""
            self.submit_requested.emit(text)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key.Key_Tab:
            self.tab_pressed.emit()
            event.accept()
            return

        if key == Qt.Key.Key_Up:
            self._history = state_manager.load_history()
            if not self._history:
                super().keyPressEvent(event)
                return

            if self._history_idx == -1:
                self._draft_text = self.text()

            if self._history_idx < len(self._history) - 1:
                self._history_idx += 1
                self.setText(self._history[self._history_idx])
                self.setCursorPosition(len(self.text()))
            event.accept()
            return

        if key == Qt.Key.Key_Down:
            if self._history_idx > 0:
                self._history_idx -= 1
                self.setText(self._history[self._history_idx])
                self.setCursorPosition(len(self.text()))
                event.accept()
                return
            elif self._history_idx == 0:
                self._history_idx = -1
                self.setText(self._draft_text)
                self.setCursorPosition(len(self.text()))
                event.accept()
                return

        super().keyPressEvent(event)


class SearchBar(QWidget):
    """Composite search bar with 3-mode pill, model selector, prompt input, and spinner."""

    prompt_submitted = Signal(str)
    mode_changed = Signal(str)
    model_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 6)
        layout.setSpacing(8)

        # Mode pill
        self.mode_pill = ModePill()
        self.mode_pill.mode_toggled.connect(self._on_mode_toggled)
        layout.addWidget(self.mode_pill)

        # Model selector
        self.model_selector = ModelSelector()
        self.model_selector.model_changed.connect(self.model_changed.emit)
        layout.addWidget(self.model_selector)

        # Prompt input
        self.input = PromptInput()
        self.input.submit_requested.connect(self.prompt_submitted.emit)
        self.input.tab_pressed.connect(self.mode_pill.toggle)
        layout.addWidget(self.input, stretch=1)

        # Spinner
        self.spinner = SpinnerLabel()
        layout.addWidget(self.spinner)

    def _on_mode_toggled(self, mode: str):
        self.model_selector.set_mode(mode)
        self.mode_changed.emit(mode)

    @property
    def current_mode(self) -> str:
        return self.mode_pill.mode

    def set_mode(self, mode: str):
        self.mode_pill.set_mode(mode)
        self.model_selector.set_mode(mode)

    def set_loading(self, loading: bool):
        if loading:
            self.spinner.start()
            self.input.setReadOnly(True)
            self.input.setStyleSheet(
                styles.INPUT_STYLE + f"\nQLineEdit#PromptInput {{ color: {styles.TEXT_SECONDARY}; }}"
            )
        else:
            self.spinner.stop()
            self.input.setReadOnly(False)
            self.input.setStyleSheet(styles.INPUT_STYLE)

    def clear_input(self):
        self.input.clear()

    def focus_input(self):
        self.input.setFocus()
        self.input.selectAll()
