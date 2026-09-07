"""Tests for native Windows hotkey parsing and manager."""
import sys
from unittest.mock import MagicMock, patch
import pytest

from src.hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    VK_ESCAPE,
    VK_RETURN,
    VK_SPACE,
    VK_TAB,
    GlobalHotkeyManager,
    parse_hotkey_string,
)


@pytest.mark.parametrize(
    "hotkey_str, expected_mods, expected_vk",
    [
        ("ctrl+space", MOD_NOREPEAT | MOD_CONTROL, VK_SPACE),
        ("alt+space", MOD_NOREPEAT | MOD_ALT, VK_SPACE),
        ("ctrl+shift+esc", MOD_NOREPEAT | MOD_CONTROL | MOD_SHIFT, VK_ESCAPE),
        ("win+return", MOD_NOREPEAT | MOD_WIN, VK_RETURN),
        ("super+enter", MOD_NOREPEAT | MOD_WIN, VK_RETURN),
        ("ctrl+tab", MOD_NOREPEAT | MOD_CONTROL, VK_TAB),
        ("ctrl+k", MOD_NOREPEAT | MOD_CONTROL, ord("K")),
        ("ctrl+shift+f1", MOD_NOREPEAT | MOD_CONTROL | MOD_SHIFT, 0x70),
        ("alt+f12", MOD_NOREPEAT | MOD_ALT, 0x7B),
        ("  Ctrl + Shift + Space  ", MOD_NOREPEAT | MOD_CONTROL | MOD_SHIFT, VK_SPACE),
    ],
)
def test_parse_hotkey_string_matrix(hotkey_str, expected_mods, expected_vk):
    mods, vk = parse_hotkey_string(hotkey_str)
    assert mods == expected_mods
    assert vk == expected_vk


def test_parse_hotkey_bare_key_rejected():
    with pytest.raises(ValueError, match="Bare non-function keys cannot be registered"):
        parse_hotkey_string("space")


def test_parse_hotkey_empty_rejected():
    with pytest.raises(ValueError):
        parse_hotkey_string("")


def test_global_hotkey_manager_registration():
    mgr = GlobalHotkeyManager()

    if sys.platform != "win32":
        assert mgr.register_hotkey("ctrl+space") == -1
        return

    with patch("ctypes.windll.user32.RegisterHotKey", return_value=1) as mock_reg, \
         patch("ctypes.windll.user32.UnregisterHotKey") as mock_unreg:

        hotkey_id = mgr.register_hotkey("ctrl+space")
        assert hotkey_id >= 100
        assert hotkey_id in mgr._registered_ids

        mgr.unregister_all()
        assert len(mgr._registered_ids) == 0
        mock_unreg.assert_called()


def test_global_hotkey_unregistered_filter():
    """Verify unregistered hotkey IDs do not emit hotkey_triggered signal."""
    mgr = GlobalHotkeyManager()
    mgr._registered_ids[101] = "ctrl+space"

    triggered = []
    mgr.hotkey_triggered.connect(triggered.append)

    # Trigger with unregistered ID
    res = mgr._on_native_hotkey(999)
    assert res is False
    assert triggered == []

    # Trigger with registered ID
    res = mgr._on_native_hotkey(101)
    assert res is True
    assert triggered == [101]


def test_global_hotkey_mod_norepeat_fallback():
    """Verify that if RegisterHotKey fails with MOD_NOREPEAT, it retries without MOD_NOREPEAT."""
    mgr = GlobalHotkeyManager()

    if sys.platform != "win32":
        return

    # First call fails (with MOD_NOREPEAT), second call succeeds (without MOD_NOREPEAT)
    with patch("ctypes.windll.user32.RegisterHotKey", side_effect=[0, 1]) as mock_reg, \
         patch("ctypes.windll.user32.UnregisterHotKey"):

        hotkey_id = mgr.register_hotkey("ctrl+space")
        assert hotkey_id >= 100
        assert mock_reg.call_count == 2
        # Verify first call included MOD_NOREPEAT (0x4000)
        first_call_mods = mock_reg.call_args_list[0][0][2]
        assert first_call_mods & MOD_NOREPEAT != 0
        # Verify second call stripped MOD_NOREPEAT
        second_call_mods = mock_reg.call_args_list[1][0][2]
        assert second_call_mods & MOD_NOREPEAT == 0


def test_win_native_event_filter_keyboard_interrupt():
    """Verify that if a KeyboardInterrupt occurs inside nativeEventFilter, it calls QCoreApplication.quit cleanly."""
    from src.hotkey import WinNativeEventFilter

    def raising_callback(hid):
        raise KeyboardInterrupt()

    filter_obj = WinNativeEventFilter(raising_callback)

    with patch("PySide6.QtCore.QCoreApplication.quit") as mock_quit:
        with patch("sys.platform", "win32"):
            with patch("ctypes.wintypes.MSG.from_address") as mock_msg:
                mock_msg.return_value.message = 0x0312  # WM_HOTKEY
                mock_msg.return_value.wParam = 100
                res = filter_obj.nativeEventFilter(b"windows_dispatcher_MSG", 12345)
                assert res is False
                mock_quit.assert_called_once()


def test_win_native_event_filter_null_message():
    """Verify that empty/null pointers in nativeEventFilter return False safely."""
    from src.hotkey import WinNativeEventFilter
    filter_obj = WinNativeEventFilter(lambda hid: True)
    assert filter_obj.nativeEventFilter(b"windows_dispatcher_MSG", 0) is False
    assert filter_obj.nativeEventFilter(b"windows_dispatcher_MSG", None) is False


