"""Markdown result viewer with horizontal citation scroll area and high-performance streaming."""
import webbrowser
from typing import Dict, List

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import styles


class SourceChip(QPushButton):
    """Clickable citation pill linking to a grounded search source."""

    def __init__(self, title: str, url: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SourceChip")
        self.url = url
        display_title = title if len(title) <= 36 else title[:33] + "..."
        self.setText(f"🔗 {display_title}")
        self.setStyleSheet(styles.SOURCE_CHIP_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(f"{title}\n{url}")
        self.clicked.connect(self._open)

    def _open(self):
        if self.url:
            webbrowser.open(self.url)


class SourcesBar(QScrollArea):
    """Horizontal scrollable row of citation chips."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFixedHeight(36)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"\n{styles.SCROLLBAR_STYLE}"
        )

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(14, 2, 14, 2)
        self._layout.setSpacing(6)
        self._layout.addStretch()
        self.setWidget(self._container)
        self.hide()

    def set_sources(self, sources: list):
        self.clear()
        if not sources:
            return

        for src in sources:
            chip = SourceChip(src.get("title", "Source"), src.get("url", ""), parent=self._container)
            self._layout.insertWidget(self._layout.count() - 1, chip)
        self.show()

    def clear(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.hide()
                w.deleteLater()
        self.hide()


class ResultView(QWidget):
    """Scrollable markdown result view with throttled streaming and link navigation."""

    content_resized = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._pending_chunks: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Status label (e.g., "🌐 Searching Google...")
        self.status_label = QLabel(self)
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setStyleSheet(styles.STATUS_LABEL_STYLE)
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        # Main markdown text browser
        self.text_view = QTextBrowser(self)
        self.text_view.setObjectName("ResultView")
        self.text_view.setStyleSheet(styles.RESULT_VIEW_STYLE + "\n" + styles.SCROLLBAR_STYLE)
        self.text_view.setReadOnly(True)
        self.text_view.setOpenExternalLinks(True)
        self.text_view.setUndoRedoEnabled(False)  # Disable undo history to prevent RAM bloat
        self.text_view.setFont(QFont("Segoe UI", 13))
        self.text_view.setMinimumHeight(40)
        self.text_view.hide()
        layout.addWidget(self.text_view, stretch=1)

        # Sources Bar
        self.sources_bar = SourcesBar(self)
        layout.addWidget(self.sources_bar)

        # Throttled flush timer for smooth 30fps text rendering without O(N^2) markdown re-parsing
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(33)
        self._flush_timer.timeout.connect(self._flush_pending_chunks)

        self.hide()

    def append_chunk(self, chunk: str):
        """Buffers streaming chunks and flushes via fast text cursor."""
        self._full_text += chunk
        self._pending_chunks.append(chunk)

        if not self.isVisible():
            self.show()
        if not self.text_view.isVisible():
            self.text_view.show()

        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_pending_chunks(self):
        if not self._pending_chunks:
            self._flush_timer.stop()
            return

        buffered = "".join(self._pending_chunks)
        self._pending_chunks.clear()

        scrollbar = self.text_view.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 20)

        cursor = self.text_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(buffered)

        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

        self.content_resized.emit()

    def finalize_markdown(self):
        """Performs a single complete markdown rendering when generation is complete."""
        self._flush_timer.stop()
        self._pending_chunks.clear()

        if self._full_text:
            scrollbar = self.text_view.verticalScrollBar()
            was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 20)

            self.text_view.setMarkdown(self._full_text)

            if was_at_bottom:
                scrollbar.setValue(scrollbar.maximum())

        self.content_resized.emit()

    def set_status(self, status: str):
        if status:
            self.status_label.setText(status)
            self.status_label.show()
            if not self.isVisible():
                self.show()
        else:
            self.status_label.hide()
        self.content_resized.emit()

    def set_sources(self, sources: list):
        self.sources_bar.set_sources(sources)
        self.content_resized.emit()

    def get_text(self) -> str:
        return self._full_text

    def get_selected_text(self) -> str:
        cursor = self.text_view.textCursor()
        return cursor.selectedText() if cursor.hasSelection() else ""

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        if not self.isVisible():
            return base
        doc_height = int(self.text_view.document().size().height())
        extra = 24
        if self.status_label.isVisible():
            extra += self.status_label.sizeHint().height() + 8
        if self.sources_bar.isVisible():
            extra += self.sources_bar.sizeHint().height() + 8
        total_h = max(base.height(), doc_height + extra)
        return QSize(base.width(), min(total_h, 640))

    def clear(self):
        self._flush_timer.stop()
        self._pending_chunks.clear()
        self._full_text = ""
        self.text_view.clear()
        self.text_view.document().clear()
        self.text_view.hide()
        self.status_label.hide()
        self.sources_bar.clear()
        self.hide()
        self.content_resized.emit()


