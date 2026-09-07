"""Unit tests for QuickLaunch AI UI widgets and components."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.ui.search_bar import ModePill, ModelSelector, PromptInput, SearchBar
from src.ui.thought_view import ThoughtView
from src.ui.result_view import ResultView
from src.ui.status_bar import StatusBar
from src.config import config


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_model_selector_behavior(qapp):
    """Verify ModelSelector updates displayed label and config based on mode."""
    selector = ModelSelector()
    selector.set_mode("simple")
    selector._select_model("gemini-2.5-pro")
    assert config.simple_model == "gemini-2.5-pro"
    assert "2.5-pro" in selector.text()

    selector.set_mode("agent")
    selector._select_model("gemini-3.5-flash")
    assert config.agent_model == "gemini-3.5-flash"
    assert "3.5-flash" in selector.text()

    selector.set_mode("cli")
    selector._select_model("")
    assert config.cli_model == ""
    assert "default" in selector.text()



def test_mode_pill_cycling(qapp):
    """Verify ModePill cycles through simple -> agent -> cli -> simple."""
    pill = ModePill()
    modes_seen = [pill.mode]

    pill.toggle()
    modes_seen.append(pill.mode)

    pill.toggle()
    modes_seen.append(pill.mode)

    pill.toggle()
    modes_seen.append(pill.mode)

    assert modes_seen == ["simple", "agent", "cli", "simple"]

    pill.set_mode("cli")
    assert pill.mode == "cli"
    assert "CLI" in pill.text()


def test_prompt_input_key_navigation(qapp):
    """Verify PromptInput handles Tab and Up/Down navigation without crashing."""
    prompt_input = PromptInput()
    tab_emitted = []

    prompt_input.tab_pressed.connect(lambda: tab_emitted.append(True))

    # Test Tab key
    key_tab = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
    prompt_input.keyPressEvent(key_tab)
    assert len(tab_emitted) == 1

    # Test Up key navigation
    key_up = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
    prompt_input.keyPressEvent(key_up)

    # Test Down key navigation
    key_down = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    prompt_input.keyPressEvent(key_down)


def test_search_bar_signals(qapp):
    """Verify SearchBar correctly handles submissions and mode switches."""
    search_bar = SearchBar()
    submitted = []
    mode_changes = []

    search_bar.prompt_submitted.connect(submitted.append)
    search_bar.mode_changed.connect(mode_changes.append)

    search_bar.input.setText("Calculate 42 * 42")
    assert search_bar.input.text() == "Calculate 42 * 42"

    search_bar.input._on_return()
    assert submitted == ["Calculate 42 * 42"]

    search_bar.mode_pill.toggle()
    assert len(mode_changes) == 1
    assert mode_changes[0] == "agent"

    search_bar.clear_input()
    assert search_bar.input.text() == ""


def test_thought_view_expand_collapse(qapp):
    """Verify ThoughtView appends thoughts and toggles collapse."""
    thought_view = ThoughtView()
    thought_view.append_thought("Analyzing requirements...\n")
    thought_view.append_thought("Selecting tool...\n")

    assert thought_view._thought_text != ""
    assert "Analyzing requirements..." in thought_view.text_view.toPlainText()

    # Toggle open
    thought_view._toggle()
    assert thought_view._expanded is True
    assert thought_view.text_view.isVisible() is True

    # Toggle closed
    thought_view._toggle()
    assert thought_view._expanded is False
    assert thought_view.text_view.isVisible() is False

    thought_view.clear()
    assert thought_view._thought_text == ""
    assert thought_view.isVisible() is False


def test_result_view_rendering_and_sources(qapp):
    """Verify ResultView streams chunks, finalizes markdown, and displays source citations."""
    result_view = ResultView()
    result_view.append_chunk("# QuickLaunch\n")
    result_view.append_chunk("Fast **Spotlight** launcher.")
    result_view.finalize_markdown()

    assert "QuickLaunch" in result_view._full_text
    assert "Spotlight" in result_view._full_text

    # Set sources
    sources = [
        {"title": "Gemini Docs", "url": "https://ai.google.dev"},
        {"title": "PySide6 Qt", "url": "https://doc.qt.io"},
    ]
    result_view.set_sources(sources)
    assert result_view.sources_bar.isVisible() is True
    assert result_view.sources_bar._layout.count() == 3  # 2 chips + 1 stretch

    # Clear
    result_view.clear()
    assert result_view._full_text == ""
    assert result_view.sources_bar.isVisible() is False


def test_status_bar_modes(qapp):
    """Verify StatusBar displays mode label updates."""
    status_bar = StatusBar()
    status_bar.set_mode("cli")
    assert "CLI" in status_bar.mode_label.text()

    status_bar.set_mode("agent")
    assert "Agent" in status_bar.mode_label.text()

    status_bar.set_mode("simple")
    assert "Simple" in status_bar.mode_label.text()
