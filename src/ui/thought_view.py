"""Collapsible thought/reasoning viewer for Agent & CLI Modes."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget

from . import styles


class ThoughtView(QWidget):
    """Expandable drawer showing the agent's internal chain-of-thought reasoning."""

    expansion_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._thought_text = ""
        self._is_finished = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toggle button
        self.toggle_btn = QPushButton("▶ 🧠 Thinking...")
        self.toggle_btn.setObjectName("ThoughtToggle")
        self.toggle_btn.setStyleSheet(styles.THOUGHT_TOGGLE_STYLE)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        # Thought text view
        self.text_view = QTextEdit()
        self.text_view.setObjectName("ThoughtView")
        self.text_view.setStyleSheet(styles.THOUGHT_VIEW_STYLE + "\n" + styles.SCROLLBAR_STYLE)
        self.text_view.setReadOnly(True)
        self.text_view.setFixedHeight(120)
        self.text_view.hide()
        layout.addWidget(self.text_view)

        self.hide()

    def append_thought(self, text: str):
        """Appends thought text and auto-scrolls only if already at bottom."""
        self._thought_text += text
        scrollbar = self.text_view.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 10)

        self.text_view.setPlainText(self._thought_text)
        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

        if not self.isVisible():
            self.show()
            self.expansion_changed.emit()
        self._update_toggle_label()

    def set_finished(self):
        """Notifies view that thought process has completed."""
        self._is_finished = True
        self._update_toggle_label()

    def clear(self):
        self._thought_text = ""
        self._is_finished = False
        self.text_view.clear()
        self._expanded = False
        self.text_view.hide()
        self.hide()
        self.expansion_changed.emit()

    def _toggle(self):
        self._expanded = not self._expanded
        self.text_view.setVisible(self._expanded)
        self._update_toggle_label()
        self.expansion_changed.emit()

    def _update_toggle_label(self):
        arrow = "▼" if self._expanded else "▶"
        if self._is_finished:
            words = len(self._thought_text.split())
            self.toggle_btn.setText(f"{arrow} 🧠 Reasoning complete ({words} words)")
        elif self._expanded:
            self.toggle_btn.setText(f"{arrow} 🧠 Live Reasoning")
        elif self._thought_text:
            preview = self._thought_text.replace("\n", " ").strip()[:50]
            self.toggle_btn.setText(f"{arrow} 🧠 Thinking... {preview}...")
        else:
            self.toggle_btn.setText(f"{arrow} 🧠 Thinking...")
