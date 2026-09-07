"""Tests for movable floating launcher window functionality."""
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from src.ui.launcher_window import LauncherWindow
from src.ui.tray import SystemTrayManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def launcher(qapp):
    window = LauncherWindow()
    window._position_on_screen()
    window.show()
    yield window
    window.dismiss()
    window.close()


def test_drag_handle_properties(launcher):
    """Verify DragHandle has correct cursor and tooltip."""
    assert launcher.drag_handle is not None
    assert launcher.drag_handle.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert "Drag to move" in launcher.drag_handle.toolTip()
    assert "Double-click to re-center" in launcher.drag_handle.toolTip()


def test_status_bar_properties(launcher):
    """Verify StatusBar has drag cursor and tooltip."""
    assert launcher.status_bar.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert "Drag to move" in launcher.status_bar.toolTip()


def test_drag_via_drag_handle(qapp, launcher):
    """Verify dragging via the top drag handle moves the window."""
    initial_pos = launcher.pos()
    handle = launcher.drag_handle

    p_press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(18, 6),
        QPointF(initial_pos.x() + 395, initial_pos.y() + 16),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(handle, p_press)

    p_move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(48, 26),
        QPointF(initial_pos.x() + 425, initial_pos.y() + 36),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(handle, p_move)

    p_release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(48, 26),
        QPointF(initial_pos.x() + 425, initial_pos.y() + 36),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(handle, p_release)

    new_pos = launcher.pos()
    assert new_pos.x() == initial_pos.x() + 30
    assert new_pos.y() == initial_pos.y() + 20
    assert launcher._user_moved is True
    assert launcher._drag_pos is None


def test_drag_via_status_bar(qapp, launcher):
    """Verify dragging via the status bar moves the window."""
    initial_pos = launcher.pos()
    status_bar = launcher.status_bar

    p_press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(20, 10),
        QPointF(initial_pos.x() + 40, initial_pos.y() + 90),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(status_bar, p_press)

    p_move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(60, 40),
        QPointF(initial_pos.x() + 80, initial_pos.y() + 120),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(status_bar, p_move)

    p_release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(60, 40),
        QPointF(initial_pos.x() + 80, initial_pos.y() + 120),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(status_bar, p_release)

    new_pos = launcher.pos()
    assert new_pos.x() == initial_pos.x() + 40
    assert new_pos.y() == initial_pos.y() + 30
    assert launcher._user_moved is True


def test_input_does_not_drag_window(qapp, launcher):
    """Verify clicking and dragging in PromptInput does NOT move the window."""
    initial_pos = launcher.pos()
    prompt_input = launcher.search_bar.input

    p_press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(50, 20),
        QPointF(initial_pos.x() + 150, initial_pos.y() + 30),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(prompt_input, p_press)

    p_move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(100, 20),
        QPointF(initial_pos.x() + 200, initial_pos.y() + 30),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(prompt_input, p_move)

    assert launcher.pos() == initial_pos
    assert launcher._user_moved is False


def test_position_preservation_across_summon(launcher):
    """Verify moved position is preserved across dismiss and summon."""
    launcher.move(450, 250)
    launcher._user_moved = True

    launcher.dismiss()
    assert not launcher.isVisible()

    launcher.summon()
    assert launcher.isVisible()
    assert launcher.pos().x() == 450
    assert launcher.pos().y() == 250


def test_recenter(launcher):
    """Verify recenter() restores default centered coordinates."""
    launcher.recenter()
    center_pos = launcher.pos()

    # Move to new position
    launcher.move(500, 300)
    launcher._user_moved = True
    assert launcher.pos() != center_pos

    # Recenter
    launcher.recenter()
    assert launcher._user_moved is False
    assert launcher.pos() == center_pos


def test_double_click_recenter(qapp, launcher):
    """Verify double clicking drag handle re-centers the window."""
    launcher.recenter()
    center_pos = launcher.pos()

    launcher.move(500, 300)
    launcher._user_moved = True

    dbl_click = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPointF(18, 6),
        QPointF(launcher.pos().x() + 395, launcher.pos().y() + 16),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(launcher.drag_handle, dbl_click)

    assert launcher.pos() == center_pos
    assert launcher._user_moved is False


def test_tray_center_window_action(qapp, launcher):
    """Verify SystemTrayManager includes 'Center Window' action when on_recenter is provided."""
    recenter_called = False

    def on_rec():
        nonlocal recenter_called
        recenter_called = True

    tray = SystemTrayManager(
        on_show=lambda: None,
        on_toggle_mode=lambda: None,
        on_clear=lambda: None,
        on_quit=lambda: None,
        on_recenter=on_rec,
    )

    menu = tray._tray.contextMenu()
    action_texts = [act.text() for act in menu.actions()]
    assert "Center Window" in action_texts

    # Trigger action
    center_action = next(act for act in menu.actions() if act.text() == "Center Window")
    center_action.trigger()
    assert recenter_called is True
