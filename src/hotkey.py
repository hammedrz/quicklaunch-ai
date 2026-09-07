"""Native Windows Global Hotkey handler using Win32 API and PySide6 QAbstractNativeEventFilter."""
import ctypes
from ctypes import wintypes
import logging
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

logger = logging.getLogger("QuickLaunch.Hotkey")

# Win32 Constants
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Win32 Error Codes
ERROR_SUCCESS = 0
ERROR_INVALID_PARAMETER = 87
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

# Virtual Key Codes
VK_SPACE = 0x20
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B

VK_MAP: Dict[str, int] = {
    # Whitespace & Control
    "space": 0x20, "spacebar": 0x20,
    "tab": 0x09,
    "enter": 0x0D, "return": 0x0D,
    "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "back": 0x08,
    "delete": 0x2E, "del": 0x2E,
    "insert": 0x2D, "ins": 0x2D,
    # Navigation
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pgup": 0x21,
    "pagedown": 0x22, "pgdn": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    # OEM & Punctuation Keys
    "`": 0xC0, "grave": 0xC0, "backtick": 0xC0, "tilde": 0xC0,
    "-": 0xBD, "minus": 0xBD,
    "=": 0xBB, "equal": 0xBB, "equals": 0xBB,
    "[": 0xDB, "bracketleft": 0xDB,
    "]": 0xDD, "bracketright": 0xDD,
    "\\": 0xDC, "backslash": 0xDC,
    ";": 0xBA, "semicolon": 0xBA,
    "'": 0xDE, "quote": 0xDE, "apostrophe": 0xDE,
    ",": 0xBC, "comma": 0xBC,
    ".": 0xBE, "period": 0xBE, "dot": 0xBE,
    "/": 0xBF, "slash": 0xBF,
    "+": 0xBB, "plus": 0xBB,
}

# Add Function keys F1-F24
for _i in range(1, 25):
    VK_MAP[f"f{_i}"] = 0x70 + (_i - 1)

# Low-Level Hook Constants & Win32 Event Codes
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Additional Modifier Virtual Key Codes for Low-Level Hook
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_SHIFT = 0x10
VK_LWIN = 0x5B
VK_RWIN = 0x5C


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


# Win32 Function Prototypes
if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL

    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK

    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL

    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = ctypes.c_longlong

    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = wintypes.SHORT

    user32.GetKeyState.argtypes = [ctypes.c_int]
    user32.GetKeyState.restype = wintypes.SHORT


def _safe_int(val, default: int = 0) -> int:
    """Safely converts value to int, avoiding exceptions if mocked or unexpected type."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _describe_modifiers(modifiers: int) -> str:
    """Returns a readable string representation of Win32 hotkey modifiers."""
    parts = []
    if modifiers & MOD_CONTROL:
        parts.append("CTRL")
    if modifiers & MOD_ALT:
        parts.append("ALT")
    if modifiers & MOD_SHIFT:
        parts.append("SHIFT")
    if modifiers & MOD_WIN:
        parts.append("WIN")
    if modifiers & MOD_NOREPEAT:
        parts.append("NOREPEAT")
    return " + ".join(parts) if parts else "NONE"


def _describe_vk(vk_code: int) -> str:
    """Returns a human-readable name for a virtual key code."""
    for name, code in VK_MAP.items():
        if code == vk_code:
            return f"{name.upper()} (0x{vk_code:02X})"
    if 0x41 <= vk_code <= 0x5A:
        return f"'{chr(vk_code)}' (0x{vk_code:02X})"
    if 0x30 <= vk_code <= 0x39:
        return f"'{chr(vk_code)}' (0x{vk_code:02X})"
    return f"0x{vk_code:02X}"


def _describe_win32_error(err_code: int) -> str:
    """Formats Win32 GetLastError code with actionable explanation."""
    if err_code == ERROR_HOTKEY_ALREADY_REGISTERED:
        return (
            f"ERROR_HOTKEY_ALREADY_REGISTERED ({err_code}): "
            "Hotkey is already registered by another application (e.g. IDE, Windows system shortcut, IME, or PowerToys)."
        )
    if err_code == ERROR_INVALID_PARAMETER:
        return f"ERROR_INVALID_PARAMETER ({err_code}): Invalid parameter or modifier/key combination."
    try:
        msg = ctypes.FormatError(err_code).strip()
        return f"Win32 Error {err_code}: {msg}"
    except Exception:
        return f"Win32 Error {err_code}"


def parse_hotkey_string(hotkey_str: str) -> Tuple[int, int]:
    """Parses a hotkey string into Win32 (modifiers, vk_code).

    Requires at least one modifier unless using an F1-F24 function key.
    Raises ValueError if the hotkey string cannot be safely parsed.
    """
    logger.debug("[Hotkey][Step 1: Parsing] Parsing hotkey string: '%s'", hotkey_str)

    if not hotkey_str or not hotkey_str.strip():
        logger.error("[Hotkey][Step 1: Parse Error] Hotkey string cannot be empty.")
        raise ValueError("Hotkey string cannot be empty.")

    normalized = hotkey_str.lower().strip().replace("-", "+")
    raw_tokens = [t.strip() for t in normalized.split("+") if t.strip()]

    if not raw_tokens:
        logger.error("[Hotkey][Step 1: Parse Error] No valid tokens found in hotkey string: '%s'", hotkey_str)
        raise ValueError(f"No valid tokens found in hotkey string: '{hotkey_str}'")

    modifiers = MOD_NOREPEAT
    vk_code = 0
    has_modifier = False

    for token in raw_tokens:
        if token in ("alt", "menu", "option", "opt"):
            modifiers |= MOD_ALT
            has_modifier = True
        elif token in ("ctrl", "control", "ctl"):
            modifiers |= MOD_CONTROL
            has_modifier = True
        elif token in ("shift", "shft"):
            modifiers |= MOD_SHIFT
            has_modifier = True
        elif token in ("win", "windows", "super", "cmd", "meta"):
            modifiers |= MOD_WIN
            has_modifier = True
        elif token in VK_MAP:
            vk_code = VK_MAP[token]
        elif len(token) == 1 and token.isalnum():
            vk_code = ord(token.upper())
        else:
            logger.error(
                "[Hotkey][Step 1: Parse Error] Unrecognized key or modifier '%s' in hotkey string '%s'",
                token,
                hotkey_str,
            )
            raise ValueError(f"Unrecognized key or modifier '{token}' in hotkey string '{hotkey_str}'")

    if vk_code == 0:
        logger.error("[Hotkey][Step 1: Parse Error] No key code specified in hotkey string: '%s'", hotkey_str)
        raise ValueError(f"No key code specified in hotkey string: '{hotkey_str}'")

    is_f_key = 0x70 <= vk_code <= 0x87
    if not has_modifier and not is_f_key:
        logger.error(
            "[Hotkey][Step 1: Parse Error] Unsafe hotkey '%s': Bare non-function keys cannot be registered globally.",
            hotkey_str,
        )
        raise ValueError(f"Unsafe hotkey '{hotkey_str}': Bare non-function keys cannot be registered globally.")

    logger.info(
        "[Hotkey][Step 1: Parsing OK] Parsed '%s' -> Modifiers: 0x%04X (%s), VK: 0x%02X (%s)",
        hotkey_str,
        modifiers,
        _describe_modifiers(modifiers),
        vk_code,
        _describe_vk(vk_code),
    )
    return modifiers, vk_code


class WinNativeEventFilter(QAbstractNativeEventFilter):
    """Filters native Windows messages to intercept WM_HOTKEY reliably."""

    def __init__(self, callback: Callable[[int], bool]):
        super().__init__()
        self.callback = callback
        self._first_msg_seen = False

    def nativeEventFilter(self, event_type, message):
        try:
            if sys.platform == "win32":
                evt = event_type.data() if hasattr(event_type, "data") else event_type
                if isinstance(evt, str):
                    evt = evt.encode("ascii", "ignore")
                elif not isinstance(evt, (bytes, bytearray)):
                    try:
                        evt = bytes(evt)
                    except Exception:
                        evt = b""

                if not self._first_msg_seen:
                    self._first_msg_seen = True
                    logger.debug(
                        "[Hotkey][Step 4: Event Pipeline Active] nativeEventFilter received first Windows message "
                        "(eventType=%s). Windows message dispatch is connected.",
                        evt.decode("ascii", "ignore"),
                    )

                # Qt 6 on Windows dispatches thread messages as windows_dispatcher_MSG
                # and window messages as windows_generic_MSG
                if evt in (b"windows_dispatcher_MSG", b"windows_generic_MSG") or b"msg" in evt.lower():
                    if not message:
                        return False
                    ptr = int(message)
                    if ptr == 0:
                        return False
                    msg = wintypes.MSG.from_address(ptr)
                    msg_id = getattr(msg, "message", 0)
                    if msg_id == WM_HOTKEY:
                        hotkey_id = _safe_int(getattr(msg, "wParam", 0))
                        hwnd_val = _safe_int(getattr(msg, "hWnd", 0))
                        lparam_val = _safe_int(getattr(msg, "lParam", 0))
                        lparam_mods = lparam_val & 0xFFFF
                        lparam_vk = (lparam_val >> 16) & 0xFFFF

                        logger.info(
                            "[Hotkey][Step 4: OS Event Intercepted] WM_HOTKEY (0x0312) received from Windows OS! "
                            "hWnd=0x%X, Hotkey ID (wParam)=%d, lParam=0x%08X (mods=0x%04X, vk=0x%04X)",
                            hwnd_val,
                            hotkey_id,
                            lparam_val,
                            lparam_mods,
                            lparam_vk,
                        )

                        consumed = self.callback(hotkey_id)
                        if consumed:
                            logger.info(
                                "[Hotkey][Step 4: OS Event Handled] WM_HOTKEY ID %d was accepted and consumed.",
                                hotkey_id,
                            )
                            return True  # Handled & consumed
                        else:
                            logger.warning(
                                "[Hotkey][Step 4: OS Event Rejected] WM_HOTKEY ID %d was not handled by manager.",
                                hotkey_id,
                            )
        except KeyboardInterrupt:
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.quit()
            return False
        except Exception as err:
            logger.error(
                "[Hotkey][Step 4: Filter Error] Unexpected exception in nativeEventFilter: %s",
                err,
                exc_info=True,
            )
        return False


class GlobalHotkeyManager(QObject):
    """Manages global hotkey registration, fallback handling, and native event filtering."""

    hotkey_triggered = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter: Optional[WinNativeEventFilter] = None
        self._registered_ids: Dict[int, str] = {}
        self._hotkey_targets: Dict[int, Tuple[int, int, str]] = {}  # id -> (mods, vk, name)
        self._current_id = 100
        self._app = None
        self._active_hotkey: Optional[str] = None
        self._last_trigger_time = 0.0
        self._hook_handle = None
        self._hook_c_proc = None

    @property
    def active_hotkey(self) -> Optional[str]:
        return self._active_hotkey

    def start(self, q_app) -> None:
        """Installs the native event filter and low-level keyboard hook on the application."""
        self._app = q_app
        if sys.platform == "win32":
            if self._filter is None:
                logger.info("[Hotkey][Step 2: Event Filter] Installing WinNativeEventFilter on QApplication...")
                self._filter = WinNativeEventFilter(self._on_native_hotkey)
                self._app.installNativeEventFilter(self._filter)
                logger.info("[Hotkey][Step 2: Event Filter OK] Native event filter successfully installed on application.")

            if self._hook_handle is None:
                try:
                    logger.info("[Hotkey][Step 2: Low-Level Hook] Installing Low-Level Keyboard Hook (WH_KEYBOARD_LL)...")
                    self._hook_c_proc = HOOKPROC(self._ll_keyboard_proc)
                    hmod = kernel32.GetModuleHandleW(None)
                    self._hook_handle = user32.SetWindowsHookExW(
                        WH_KEYBOARD_LL,
                        self._hook_c_proc,
                        hmod,
                        0,
                    )
                    if self._hook_handle:
                        logger.info(
                            "[Hotkey][Step 2: Low-Level Hook OK] Low-Level Keyboard Hook installed successfully (handle=%s). "
                            "Protects against Windows IME, language bar, and IDE shortcut interception.",
                            self._hook_handle,
                        )
                    else:
                        err = kernel32.GetLastError()
                        logger.warning(
                            "[Hotkey][Step 2: Low-Level Hook Warning] SetWindowsHookExW returned 0 (Win32 Err: %d). "
                            "Relying on WinNativeEventFilter.",
                            err,
                        )
                except Exception as err:
                    logger.warning("[Hotkey][Step 2: Low-Level Hook Warning] Failed to install WH_KEYBOARD_LL: %s", err)
        else:
            logger.warning(
                "[Hotkey][Step 2: Event Filter] Platform is '%s' (not win32). Global native hotkeys are unsupported.",
                sys.platform,
            )

    def stop(self) -> None:
        """Unregisters all hotkeys, removes the low-level hook, and removes the native event filter cleanly."""
        logger.info("[Hotkey] Stopping GlobalHotkeyManager and unregistering all hotkeys...")
        self.unregister_all()
        if sys.platform == "win32" and self._hook_handle:
            try:
                user32.UnhookWindowsHookEx(self._hook_handle)
                logger.info("[Hotkey] Low-Level Keyboard Hook (WH_KEYBOARD_LL) removed.")
            except Exception as err:
                logger.warning("[Hotkey] Error removing Low-Level Keyboard Hook: %s", err)
            self._hook_handle = None
        self._hook_c_proc = None

        if self._app and self._filter:
            try:
                self._app.removeNativeEventFilter(self._filter)
                logger.info("[Hotkey] Native event filter removed from application.")
            except Exception as err:
                logger.warning("[Hotkey] Error removing native event filter: %s", err)
            self._filter = None
        self._app = None

    def register_hotkey(self, hotkey_str: str) -> int:
        """Registers a global hotkey across Windows. Returns the ID, or -1 on failure."""
        if sys.platform != "win32":
            logger.warning(
                "[Hotkey][Step 3: Registration] Platform '%s' does not support Win32 global hotkeys.",
                sys.platform,
            )
            return -1

        try:
            modifiers, vk_code = parse_hotkey_string(hotkey_str)
        except ValueError as err:
            print(f"[Hotkey Error] {err}")
            return -1

        hotkey_id = self._current_id
        mods_desc = _describe_modifiers(modifiers)
        vk_desc = _describe_vk(vk_code)

        logger.info(
            "[Hotkey][Step 3: Registration] Invoking Win32 RegisterHotKey: '%s' (ID %d) -> "
            "Modifiers=0x%04X (%s), VK=0x%02X (%s)...",
            hotkey_str,
            hotkey_id,
            modifiers,
            mods_desc,
            vk_code,
            vk_desc,
        )

        kernel32.SetLastError(ERROR_SUCCESS)
        success = user32.RegisterHotKey(None, hotkey_id, modifiers, vk_code)

        if not success and (modifiers & MOD_NOREPEAT):
            retry_mods = modifiers & ~MOD_NOREPEAT
            logger.warning(
                "[Hotkey][Step 3: Registration Retry] Initial RegisterHotKey failed with MOD_NOREPEAT. "
                "Retrying without MOD_NOREPEAT for '%s' (Modifiers=0x%04X)...",
                hotkey_str,
                retry_mods,
            )
            # Fallback retry without MOD_NOREPEAT (crucial on Windows with certain IMEs or keyboard layouts)
            success = user32.RegisterHotKey(None, hotkey_id, retry_mods, vk_code)

        if success:
            self._current_id += 1
            self._registered_ids[hotkey_id] = hotkey_str
            self._hotkey_targets[hotkey_id] = (modifiers, vk_code, hotkey_str)
            self._active_hotkey = hotkey_str
            logger.info(
                "[Hotkey][Step 3: Registration SUCCESS] Hotkey '%s' successfully registered with Win32 ID %d! "
                "Active hotkey is now '%s'.",
                hotkey_str,
                hotkey_id,
                hotkey_str,
            )
            return hotkey_id

        err_code = kernel32.GetLastError()
        err_desc = _describe_win32_error(err_code)

        if err_code == ERROR_HOTKEY_ALREADY_REGISTERED:
            logger.warning(
                "[Hotkey][Step 3: Registration CONFLICT] Hotkey '%s' (ID %d) registration failed: %s",
                hotkey_str,
                hotkey_id,
                err_desc,
            )
            print(f"[Hotkey Conflict] Hotkey '{hotkey_str}' is already registered by another application.")
        elif err_code == ERROR_INVALID_PARAMETER:
            logger.error(
                "[Hotkey][Step 3: Registration ERROR] Hotkey '%s' (ID %d) registration failed: %s",
                hotkey_str,
                hotkey_id,
                err_desc,
            )
            print(f"[Hotkey Error] Invalid parameters for hotkey '{hotkey_str}'.")
        else:
            logger.error(
                "[Hotkey][Step 3: Registration ERROR] Hotkey '%s' (ID %d) registration failed: %s",
                hotkey_str,
                hotkey_id,
                err_desc,
            )
            print(f"[Hotkey Error] Failed to register '{hotkey_str}' (Win32 Error: {err_code}).")

        return -1

    def register_with_fallbacks(self, preferred: str, fallbacks: List[str]) -> Tuple[int, Optional[str]]:
        """Registers the preferred hotkey as primary and registers fallback keys as active alternate triggers.

        Returns (primary_id, primary_name).
        """
        logger.info(
            "[Hotkey][Step 3: Registration Sequence] Beginning registration sequence. "
            "Preferred: '%s', Fallbacks: %s",
            preferred,
            fallbacks,
        )

        # 1. Attempt preferred hotkey
        primary_id = self.register_hotkey(preferred)
        primary_name = preferred if primary_id >= 0 else None

        active_alternates: List[str] = []
        # 2. Register fallbacks as active alternates if preferred succeeded,
        #    or find first succeeding candidate as primary if preferred failed.
        for candidate in fallbacks:
            if candidate.lower() == preferred.lower():
                continue
            hid = self.register_hotkey(candidate)
            if hid >= 0:
                if primary_id < 0:
                    primary_id = hid
                    primary_name = candidate
                    logger.warning(
                        "[Hotkey][Step 3: Fallback Activated] Preferred hotkey '%s' was unavailable; "
                        "promoted fallback '%s' (Win32 ID %d) to primary hotkey.",
                        preferred,
                        candidate,
                        hid,
                    )
                else:
                    active_alternates.append(candidate)
                    logger.info(
                        "[Hotkey][Step 3: Alternate Trigger Active] Also registered alternate shortcut '%s' (Win32 ID %d).",
                        candidate,
                        hid,
                    )

        if primary_id >= 0 and primary_name:
            self._active_hotkey = primary_name
            logger.info(
                "[Hotkey][Step 3: Registration COMPLETED] Primary hotkey '%s' active (Win32 ID %d). "
                "Additional active triggers: %s",
                primary_name,
                primary_id,
                active_alternates or "None",
            )
            return primary_id, primary_name

        logger.critical(
            "[Hotkey][Step 3: All Registrations FAILED] Could not register any hotkey from candidates: %s. "
            "No global hotkey will be active! Check if another tool (e.g. IDE, PowerToys, IME) has reserved these keys.",
            [preferred] + fallbacks,
        )
        return -1, None

    def unregister_all(self) -> None:
        """Unregisters all active hotkeys cleanly."""
        if sys.platform == "win32":
            for hotkey_id, name in list(self._registered_ids.items()):
                user32.UnregisterHotKey(None, hotkey_id)
                logger.info("[Hotkey] Unregistered hotkey '%s' (ID %d)", name, hotkey_id)
        self._registered_ids.clear()
        self._hotkey_targets.clear()
        self._active_hotkey = None

    def _ll_keyboard_proc(self, nCode: int, wParam: int, lParam: int) -> int:
        """Low-level keyboard hook procedure (WH_KEYBOARD_LL).

        Runs at the lowest user-mode level, catching keys BEFORE Windows IME, language bar,
        or foreground applications can swallow them.
        """
        try:
            if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if not lParam:
                    return user32.CallNextHookEx(None, nCode, wParam, lParam)

                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                vk = kb.vkCode

                # Check active modifier keys (asynchronous hardware state + synchronous message state)
                ctrl_down = bool(
                    (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                    or (user32.GetAsyncKeyState(0xA2) & 0x8000)  # VK_LCONTROL
                    or (user32.GetAsyncKeyState(0xA3) & 0x8000)  # VK_RCONTROL
                    or (user32.GetKeyState(VK_CONTROL) & 0x8000)
                )
                alt_down = bool(
                    (user32.GetAsyncKeyState(VK_MENU) & 0x8000)  # VK_MENU
                    or (user32.GetAsyncKeyState(0xA4) & 0x8000)  # VK_LMENU
                    or (user32.GetAsyncKeyState(0xA5) & 0x8000)  # VK_RMENU
                    or (user32.GetKeyState(VK_MENU) & 0x8000)
                    or (kb.flags & 0x20)  # LLKHF_ALTDOWN
                )
                shift_down = bool(
                    (user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)  # VK_SHIFT
                    or (user32.GetAsyncKeyState(0xA0) & 0x8000)  # VK_LSHIFT
                    or (user32.GetAsyncKeyState(0xA1) & 0x8000)  # VK_RSHIFT
                    or (user32.GetKeyState(VK_SHIFT) & 0x8000)
                )
                win_down = bool(
                    (user32.GetAsyncKeyState(VK_LWIN) & 0x8000)
                    or (user32.GetAsyncKeyState(VK_RWIN) & 0x8000)
                    or (user32.GetKeyState(VK_LWIN) & 0x8000)
                    or (user32.GetKeyState(VK_RWIN) & 0x8000)
                )

                current_mods = 0
                if ctrl_down:
                    current_mods |= MOD_CONTROL
                if alt_down:
                    current_mods |= MOD_ALT
                if shift_down:
                    current_mods |= MOD_SHIFT
                if win_down:
                    current_mods |= MOD_WIN

                for hotkey_id, (target_mods, target_vk, hotkey_name) in list(self._hotkey_targets.items()):
                    clean_target_mods = target_mods & ~MOD_NOREPEAT
                    if current_mods == clean_target_mods and vk == target_vk:
                        logger.info(
                            "[Hotkey][Step 4: LL Hook Intercepted] Low-Level Keyboard Hook captured '%s' "
                            "(ID %d, VK=0x%02X, Mods=0x%04X). Emitting summon/dismiss.",
                            hotkey_name,
                            hotkey_id,
                            vk,
                            current_mods,
                        )
                        consumed = self._on_native_hotkey(hotkey_id)
                        if consumed:
                            # Swallow the keystroke so it does not leak into the active window or trigger IME
                            return 1
        except Exception as err:
            logger.error("[Hotkey] Error in low-level keyboard hook callback: %s", err, exc_info=True)

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _on_native_hotkey(self, hotkey_id: int) -> bool:
        hotkey_name = self._registered_ids.get(hotkey_id, "UNKNOWN")
        if hotkey_id in self._registered_ids:
            now = time.monotonic()
            elapsed = now - self._last_trigger_time
            if elapsed >= 0.20:
                self._last_trigger_time = now
                logger.info(
                    "[Hotkey][Step 5: Signal Dispatch] Dispatching hotkey_triggered signal for ID %d ('%s') "
                    "(elapsed since last=%.3fs)",
                    hotkey_id,
                    hotkey_name,
                    elapsed,
                )
                self.hotkey_triggered.emit(hotkey_id)
            else:
                logger.info(
                    "[Hotkey][Step 5: Debounced] Suppressed rapid duplicate trigger for ID %d ('%s') "
                    "(%.3fs < 0.200s debounce threshold)",
                    hotkey_id,
                    hotkey_name,
                    elapsed,
                )
            return True

        logger.warning(
            "[Hotkey][Step 5: Unknown ID] Received hotkey ID %d not found in active registrations: %s",
            hotkey_id,
            self._registered_ids,
        )
        return False
