"""Raycast-inspired dark theme QSS stylesheet and constants for QuickLaunch AI."""

# Color Palette (WCAG AA Compliant)
BG_PRIMARY = "#161618"
BG_SECONDARY = "#1c1c1e"
BG_CARD = "#202024"
BG_INPUT = "#222226"
BG_HOVER = "#2c2c30"
BORDER_COLOR = "#3e3e44"
BORDER_SUBTLE = "#2e2e33"

# High-contrast typography
TEXT_PRIMARY = "#f5f5f7"
TEXT_SECONDARY = "#a1a1a6"   # Contrast > 5.5:1 on #161618
TEXT_MUTED = "#86868b"       # Contrast > 4.5:1 on #161618

# Accents
ACCENT_BLUE = "#0a84ff"
ACCENT_BLUE_HOVER = "#2491ff"
ACCENT_CYAN = "#5ac8fa"
ACCENT_GREEN = "#30d158"
ACCENT_PURPLE = "#bf5af2"
ACCENT_AMBER = "#ff9f0a"
ACCENT_RED = "#ff453a"

# Mode Badge Colors
SIMPLE_MODE_BG = "#132d4a"
SIMPLE_MODE_BORDER = "rgba(90, 200, 250, 0.4)"
SIMPLE_MODE_TEXT = ACCENT_CYAN

AGENT_MODE_BG = "#35144f"
AGENT_MODE_BORDER = "rgba(191, 90, 242, 0.4)"
AGENT_MODE_TEXT = ACCENT_PURPLE

CLI_MODE_BG = "#133826"
CLI_MODE_BORDER = "rgba(48, 209, 88, 0.4)"
CLI_MODE_TEXT = ACCENT_GREEN

# Dimensions
WINDOW_CORNER_RADIUS = 14
INPUT_HEIGHT = 48
STATUS_BAR_HEIGHT = 32
DRAG_HANDLE_HEIGHT = 16

# Main Window QSS
WINDOW_STYLE = f"""
    QWidget#LauncherContainer {{
        background-color: {BG_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {WINDOW_CORNER_RADIUS}px;
    }}
"""

DRAG_HANDLE_STYLE = f"""
    QWidget#DragHandleBar {{
        background-color: {BORDER_COLOR};
        border-radius: 2px;
    }}
    QWidget#DragHandle:hover QWidget#DragHandleBar {{
        background-color: {TEXT_MUTED};
    }}
"""

INPUT_STYLE = f"""
    QLineEdit#PromptInput {{
        background-color: transparent;
        border: none;
        color: {TEXT_PRIMARY};
        font-size: 16px;
        font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
        padding: 0px 4px;
        selection-background-color: {ACCENT_BLUE};
    }}
    QLineEdit#PromptInput::placeholder {{
        color: {TEXT_MUTED};
    }}
"""

MODE_PILL_STYLE_SIMPLE = f"""
    QPushButton#ModePill {{
        background-color: {SIMPLE_MODE_BG};
        color: {SIMPLE_MODE_TEXT};
        border: 1px solid {SIMPLE_MODE_BORDER};
        border-radius: 9px;
        font-size: 11px;
        font-weight: 600;
        font-family: 'Segoe UI', sans-serif;
        padding: 3px 9px;
    }}
    QPushButton#ModePill:hover {{
        background-color: #1a3c63;
        border-color: {ACCENT_CYAN};
    }}
"""

MODE_PILL_STYLE_AGENT = f"""
    QPushButton#ModePill {{
        background-color: {AGENT_MODE_BG};
        color: {AGENT_MODE_TEXT};
        border: 1px solid {AGENT_MODE_BORDER};
        border-radius: 9px;
        font-size: 11px;
        font-weight: 600;
        font-family: 'Segoe UI', sans-serif;
        padding: 3px 9px;
    }}
    QPushButton#ModePill:hover {{
        background-color: #491c6e;
        border-color: {ACCENT_PURPLE};
    }}
"""

MODE_PILL_STYLE_CLI = f"""
    QPushButton#ModePill {{
        background-color: {CLI_MODE_BG};
        color: {CLI_MODE_TEXT};
        border: 1px solid {CLI_MODE_BORDER};
        border-radius: 9px;
        font-size: 11px;
        font-weight: 600;
        font-family: 'Segoe UI', sans-serif;
        padding: 3px 9px;
    }}
    QPushButton#ModePill:hover {{
        background-color: #1a4d34;
        border-color: {ACCENT_GREEN};
    }}
"""

MODEL_SELECTOR_STYLE = f"""
    QPushButton#ModelSelector {{
        background-color: {BG_CARD};
        color: {TEXT_SECONDARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 8px;
        font-size: 11px;
        font-weight: 500;
        font-family: 'Segoe UI', sans-serif;
        padding: 3px 8px;
    }}
    QPushButton#ModelSelector:hover {{
        background-color: {BG_HOVER};
        color: {TEXT_PRIMARY};
        border-color: {BORDER_COLOR};
    }}
"""


STATUS_LABEL_STYLE = f"""
    QLabel#StatusLabel {{
        color: {TEXT_SECONDARY};
        font-size: 12px;
        font-family: 'Segoe UI', sans-serif;
        padding: 4px 16px;
        background: transparent;
    }}
"""

THOUGHT_VIEW_STYLE = f"""
    QTextEdit#ThoughtView {{
        background-color: {BG_SECONDARY};
        color: {TEXT_SECONDARY};
        border: none;
        border-top: 1px solid {BORDER_SUBTLE};
        font-size: 12px;
        line-height: 1.4;
        font-family: 'Cascadia Code', 'Consolas', monospace;
        padding: 8px 16px;
        selection-background-color: rgba(191, 90, 242, 0.35);
    }}
"""

THOUGHT_TOGGLE_STYLE = f"""
    QPushButton#ThoughtToggle {{
        background-color: transparent;
        color: {TEXT_MUTED};
        border: none;
        border-top: 1px solid {BORDER_SUBTLE};
        font-size: 11px;
        font-family: 'Segoe UI', sans-serif;
        padding: 5px 16px;
        text-align: left;
    }}
    QPushButton#ThoughtToggle:hover {{
        color: {TEXT_PRIMARY};
        background-color: {BG_SECONDARY};
    }}
"""

RESULT_VIEW_STYLE = f"""
    QTextEdit#ResultView {{
        background-color: transparent;
        color: {TEXT_PRIMARY};
        border: none;
        border-top: 1px solid {BORDER_SUBTLE};
        font-size: 14px;
        font-family: 'Segoe UI', 'Inter', sans-serif;
        padding: 10px 16px;
        selection-background-color: rgba(10, 132, 255, 0.4);
    }}
"""

SOURCE_CHIP_STYLE = f"""
    QPushButton#SourceChip {{
        background-color: {BG_CARD};
        color: {ACCENT_CYAN};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 6px;
        font-size: 11px;
        font-family: 'Segoe UI', sans-serif;
        padding: 3px 8px;
    }}
    QPushButton#SourceChip:hover {{
        background-color: {BG_HOVER};
        border-color: {BORDER_COLOR};
        color: {TEXT_PRIMARY};
    }}
"""

STATUS_BAR_STYLE = f"""
    QWidget#StatusBar {{
        background-color: {BG_SECONDARY};
        border-top: 1px solid {BORDER_SUBTLE};
        border-bottom-left-radius: {WINDOW_CORNER_RADIUS}px;
        border-bottom-right-radius: {WINDOW_CORNER_RADIUS}px;
    }}
"""

STATUS_KEY_HINT_STYLE = f"""
    QLabel#KeyHint {{
        color: {TEXT_MUTED};
        font-size: 11px;
        font-family: 'Segoe UI', sans-serif;
    }}
"""

SCROLLBAR_STYLE = f"""
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_COLOR};
        border-radius: 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        height: 4px;
        background: transparent;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_COLOR};
        border-radius: 2px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
"""

MENU_STYLE = f"""
    QMenu {{
        background-color: {BG_SECONDARY};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        padding: 4px;
        color: {TEXT_PRIMARY};
        font-family: 'Segoe UI', sans-serif;
        font-size: 12px;
    }}
    QMenu::item {{
        padding: 6px 20px 6px 12px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {ACCENT_BLUE};
        color: #ffffff;
    }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER_SUBTLE};
        margin: 4px 6px;
    }}
"""

SPINNER_STYLE = f"""
    QLabel#Spinner {{
        color: {ACCENT_BLUE};
        font-size: 14px;
        background: transparent;
    }}
"""
