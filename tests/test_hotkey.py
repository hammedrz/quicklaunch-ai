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


def test_describe_helpers():
    """Verify modifier, VK code, and Win32 error descriptive formatters."""
    from src.hotkey import (
        _describe_modifiers,
        _describe_vk,
        _describe_win32_error,
        MOD_ALT,
        MOD_CONTROL,
        MOD_NOREPEAT,
        VK_SPACE,
        ERROR_HOTKEY_ALREADY_REGISTERED,
    )
    mods_desc = _describe_modifiers(MOD_CONTROL | MOD_NOREPEAT)
    assert "CTRL" in mods_desc
    assert "NOREPEAT" in mods_desc

    vk_desc = _describe_vk(VK_SPACE)
    assert "SPACE" in vk_desc

    vk_letter = _describe_vk(ord("K"))
    assert "'K'" in vk_letter

    err_desc = _describe_win32_error(ERROR_HOTKEY_ALREADY_REGISTERED)
    assert "ERROR_HOTKEY_ALREADY_REGISTERED" in err_desc


def test_hotkey_step_logging_during_flow(caplog):
    """Verify that every step of hotkey lifecycle logs informative messages."""
    import logging
    from src.hotkey import WinNativeEventFilter

    caplog.set_level(logging.DEBUG)

    # Step 1: Parsing
    parse_hotkey_string("ctrl+space")
    assert any("[Step 1: Parsing OK]" in r.message for r in caplog.records)

    # Step 2 & 3: Start and Register
    mgr = GlobalHotkeyManager()
    mock_app = MagicMock()
    with patch("sys.platform", "win32"):
        mgr.start(mock_app)
        assert any("[Step 2: Event Filter]" in r.message for r in caplog.records)

        with patch("ctypes.windll.user32.RegisterHotKey", return_value=1):
            hid = mgr.register_hotkey("ctrl+space")
            assert hid >= 100
            assert any("[Step 3: Registration SUCCESS]" in r.message for r in caplog.records)

        # Step 4: Event Intercepted
        callback = MagicMock(return_value=True)
        filt = WinNativeEventFilter(callback)
        with patch("ctypes.wintypes.MSG.from_address") as mock_msg:
            mock_msg.return_value.message = 0x0312
            mock_msg.return_value.wParam = hid
            mock_msg.return_value.hWnd = 0
            mock_msg.return_value.lParam = 0x00204002
            res = filt.nativeEventFilter(b"windows_dispatcher_MSG", 12345)
            assert res is True
            assert any("[Step 4: OS Event Intercepted]" in r.message for r in caplog.records)

        # Step 5: Manager Signal Dispatch
        mgr._on_native_hotkey(hid)
        assert any("[Step 5: Signal Dispatch]" in r.message for r in caplog.records)


def test_register_with_fallbacks_logging(caplog):
    """Verify fallback sequence logs each attempt and fallback activation."""
    import logging
    caplog.set_level(logging.INFO)

    mgr = GlobalHotkeyManager()
    if sys.platform != "win32":
        return

    # First candidate fails with conflict on initial and retry without MOD_NOREPEAT ([0, 0]),
    # second candidate succeeds ([1])
    with patch("ctypes.windll.user32.RegisterHotKey", side_effect=[0, 0, 1]), \
         patch("ctypes.windll.kernel32.GetLastError", return_value=1409):
        hid, candidate = mgr.register_with_fallbacks("ctrl+space", ["ctrl+shift+space"])
        assert hid >= 100
        assert candidate == "ctrl+shift+space"
        assert any("[Step 3: Fallback Activated]" in r.message for r in caplog.records)


def test_register_with_fallbacks_all_registered():
    """Verify that when preferred succeeds, fallbacks are also registered as alternate triggers."""
    mgr = GlobalHotkeyManager()
    if sys.platform != "win32":
        return

    with patch("ctypes.windll.user32.RegisterHotKey", return_value=1):
        hid, candidate = mgr.register_with_fallbacks("ctrl+space", ["ctrl+shift+space", "alt+space"])
        assert hid >= 100
        assert candidate == "ctrl+space"
        # Verify all 3 hotkeys were registered
        assert len(mgr._registered_ids) == 3
        assert any(v == "ctrl+space" for v in mgr._registered_ids.values())
        assert any(v == "ctrl+shift+space" for v in mgr._registered_ids.values())
        assert any(v == "alt+space" for v in mgr._registered_ids.values())
        mgr.unregister_all()


def test_ll_keyboard_proc_match():
    """Verify low-level hook proc correctly matches Ctrl+Space and consumes it."""
    import ctypes
    from src.hotkey import KBDLLHOOKSTRUCT, WM_KEYDOWN, VK_SPACE, VK_CONTROL

    mgr = GlobalHotkeyManager()
    if sys.platform != "win32":
        return

    mgr._registered_ids[100] = "ctrl+space"
    # mods=0x4002 (MOD_NOREPEAT | MOD_CONTROL), vk=0x20
    mgr._hotkey_targets[100] = (0x4002, VK_SPACE, "ctrl+space")

    triggered = []
    mgr.hotkey_triggered.connect(triggered.append)

    kb = KBDLLHOOKSTRUCT(vkCode=VK_SPACE, scanCode=0, flags=0, time=0, dwExtraInfo=0)
    lparam = ctypes.addressof(kb)

    # Mock GetAsyncKeyState so only VK_CONTROL is down (0x8000)
    def fake_async_key(vk):
        return -32767 if vk == VK_CONTROL else 0

    with patch("ctypes.windll.user32.GetAsyncKeyState", side_effect=fake_async_key), \
         patch("ctypes.windll.user32.GetKeyState", return_value=0), \
         patch("ctypes.windll.user32.CallNextHookEx", return_value=0) as mock_next:

        ret = mgr._ll_keyboard_proc(0, WM_KEYDOWN, lparam)
        assert ret == 1  # Consumed!
        assert triggered == [100]
        mock_next.assert_not_called()


def test_ll_keyboard_proc_unmatched_passes_through():
    """Verify low-level hook proc calls CallNextHookEx when key does not match."""
    import ctypes
    from src.hotkey import KBDLLHOOKSTRUCT, WM_KEYDOWN, VK_SPACE

    mgr = GlobalHotkeyManager()
    if sys.platform != "win32":
        return

    mgr._registered_ids[100] = "ctrl+space"
    mgr._hotkey_targets[100] = (0x4002, VK_SPACE, "ctrl+space")

    triggered = []
    mgr.hotkey_triggered.connect(triggered.append)

    kb = KBDLLHOOKSTRUCT(vkCode=ord("A"), scanCode=0, flags=0, time=0, dwExtraInfo=0)
    lparam = ctypes.addressof(kb)

    with patch("ctypes.windll.user32.GetAsyncKeyState", return_value=0), \
         patch("ctypes.windll.user32.GetKeyState", return_value=0), \
         patch("ctypes.windll.user32.CallNextHookEx", return_value=0) as mock_next:

        ret = mgr._ll_keyboard_proc(0, WM_KEYDOWN, lparam)
        assert ret == 0  # Passed through
        assert triggered == []
        mock_next.assert_called_once()




