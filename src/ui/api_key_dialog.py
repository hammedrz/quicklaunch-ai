"""In-app API key configuration dialog for QuickLaunch AI."""
import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..ai.model_registry import model_registry
from ..config import config
from . import styles


class ApiKeyDialog(QDialog):
    """Raycast-styled dialog for entering Gemini API key and selecting default models."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QuickLaunch Settings")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 330)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {styles.BG_PRIMARY};
                border: 1px solid {styles.BORDER_COLOR};
                border-radius: 12px;
            }}
            QLabel {{
                color: {styles.TEXT_PRIMARY};
                font-family: 'Segoe UI', sans-serif;
            }}
            QLineEdit, QComboBox {{
                background-color: {styles.BG_INPUT};
                border: 1px solid {styles.BORDER_COLOR};
                border-radius: 6px;
                color: {styles.TEXT_PRIMARY};
                font-size: 13px;
                padding: 6px 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {styles.BG_SECONDARY};
                color: {styles.TEXT_PRIMARY};
                selection-background-color: {styles.ACCENT_BLUE};
                border: 1px solid {styles.BORDER_COLOR};
                padding: 4px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {styles.ACCENT_BLUE};
            }}
            QPushButton {{
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel("⚙️ QuickLaunch Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Key Input
        key_label = QLabel("🔑 Gemini API Key:")
        key_label.setStyleSheet(f"color: {styles.TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Enter AIzaSy... API key")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if config.gemini_api_key:
            self.key_input.setText(config.gemini_api_key)
        layout.addWidget(self.key_input)

        # Models row
        models_layout = QHBoxLayout()
        models_layout.setSpacing(12)

        # Simple Model
        simple_box = QVBoxLayout()
        s_label = QLabel("⚡ Simple Mode Model:")
        s_label.setStyleSheet(f"color: {styles.TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        simple_box.addWidget(s_label)
        self.simple_combo = QComboBox()
        self.agent_combo = QComboBox()

        # Populate combos dynamically from model_registry
        available = model_registry.get_models("simple")
        for mid, label in available:
            self.simple_combo.addItem(label, userData=mid)
            self.agent_combo.addItem(label, userData=mid)

        # Set active selections
        for i in range(self.simple_combo.count()):
            if self.simple_combo.itemData(i) == config.simple_model:
                self.simple_combo.setCurrentIndex(i)
                break

        for i in range(self.agent_combo.count()):
            if self.agent_combo.itemData(i) == config.agent_model:
                self.agent_combo.setCurrentIndex(i)
                break

        simple_box.addWidget(self.simple_combo)
        models_layout.addLayout(simple_box)

        # Agent Model
        agent_box = QVBoxLayout()
        a_label = QLabel("🤖 Agent Mode Model:")
        a_label.setStyleSheet(f"color: {styles.TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        agent_box.addWidget(a_label)
        agent_box.addWidget(self.agent_combo)
        models_layout.addLayout(agent_box)

        layout.addLayout(models_layout)

        # Buttons row
        btn_layout = QHBoxLayout()
        get_key_btn = QPushButton("Get Key from AI Studio ↗")
        get_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        get_key_btn.setStyleSheet(f"background: transparent; color: {styles.ACCENT_BLUE}; border: none; text-align: left; font-size: 11px;")
        get_key_btn.clicked.connect(lambda: webbrowser.open("https://aistudio.google.com/app/api-keys"))
        btn_layout.addWidget(get_key_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"background-color: {styles.BG_HOVER}; color: {styles.TEXT_PRIMARY}; border: 1px solid {styles.BORDER_SUBTLE};")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"background-color: {styles.ACCENT_BLUE}; color: #ffffff; border: none;")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _save(self):
        entered = self.key_input.text().strip()
        if entered:
            config.save_api_key(entered)
            model_registry.refresh_async()

        selected_simple = self.simple_combo.currentData() or self.simple_combo.currentText()
        selected_agent = self.agent_combo.currentData() or self.agent_combo.currentText()

        if selected_simple:
            config.simple_model = selected_simple
        if selected_agent:
            config.agent_model = selected_agent

        self.accept()

