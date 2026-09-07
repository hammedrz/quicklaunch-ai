"""Status bar with contextual keyboard shortcut badges and 3-mode indicator."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from . import styles


class StatusBar(QWidget):
    """Raycast-style bottom action bar with keyboard shortcut badges."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setStyleSheet(styles.STATUS_BAR_STYLE)
        self.setFixedHeight(styles.STATUS_BAR_HEIGHT)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Drag to move • Double-click to re-center")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        self._hints = [
            ("↵", "Submit"),
            ("Tab", "Mode"),
            ("Ctrl+P", "Model"),
            ("Esc", "Close"),
            ("Ctrl+C", "Copy"),
            ("Ctrl+L", "Clear"),
        ]

        for key, label in self._hints:
            hint = QLabel(self._make_kbd_html(key, label))
            hint.setObjectName("KeyHint")
            hint.setTextFormat(Qt.TextFormat.RichText)
            hint.setStyleSheet(styles.STATUS_KEY_HINT_STYLE)
            layout.addWidget(hint)

        layout.addStretch()

        # Mode indicator on right
        self.mode_label = QLabel()
        self.mode_label.setObjectName("KeyHint")
        self.mode_label.setStyleSheet(styles.STATUS_KEY_HINT_STYLE)
        self.set_mode("simple")
        layout.addWidget(self.mode_label)

    @staticmethod
    def _make_kbd_html(key: str, label: str) -> str:
        return (
            f'<span style="background-color: #26262a; border: 1px solid #3a3a40; '
            f'border-radius: 4px; padding: 1px 5px; color: #d1d1d6; font-size: 10px; '
            f'font-weight: bold;">{key}</span> '
            f'<span style="color: #8e8e93; font-size: 11px;">{label}</span>'
        )

    def set_mode(self, mode: str):
        cleaned = mode.lower()
        if cleaned == "agent":
            self.mode_label.setText("🤖 Agent Mode")
        elif cleaned == "cli":
            self.mode_label.setText("🚀 CLI Mode")
        else:
            self.mode_label.setText("⚡ Simple Mode")
