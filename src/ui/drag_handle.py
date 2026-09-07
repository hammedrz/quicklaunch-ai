"""Subtle top drag handle for moving the frameless launcher window."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from . import styles


class DragHandle(QWidget):
    """Visual pill handle at the top of the launcher window indicating draggability."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DragHandle")
        self.setFixedHeight(styles.DRAG_HANDLE_HEIGHT)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Drag to move • Double-click to re-center")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._bar = QWidget(self)
        self._bar.setObjectName("DragHandleBar")
        self._bar.setFixedSize(38, 4)
        self._bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._bar)

        self.setStyleSheet(styles.DRAG_HANDLE_STYLE)
