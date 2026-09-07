"""Native Windows Global Hotkey handler using Win32 API and PySide6 QAbstractNativeEventFilter."""
import ctypes
from ctypes import wintypes
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal


# Win32 Constants
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Win32 Error Codes
ERROR_SUCCESS = 0
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
ERROR_INVALID_PARAMETER = 87

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

# Win32 Function Prototypes
if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL

    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL


def parse_hotkey_string(hotkey_str: str) -> Tuple[int, int]:
    """Parses a hotkey string into Win32 (modifiers, vk_code).
    
    Requires at least one modifier unless using an F1-F24 function key.
    Raises ValueError if the hotkey string cannot be safely parsed.
    """
    if not hotkey_str or not hotkey_str.strip():
        raise ValueError("Hotkey string cannot be empty.")

    normalized = hotkey_str.lower().strip().replace("-", "+")
    raw_tokens = [t.strip() for t in normalized.split("+") if t.strip()]

    if not raw_tokens:
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
            raise ValueError(f"Unrecognized key or modifier '{token}' in hotkey string '{hotkey_str}'")

    if vk_code == 0:
        raise ValueError(f"No key code specified in hotkey string: '{hotkey_str}'")

    is_f_key = 0x70 <= vk_code <= 0x87
    if not has_modifier and not is_f_key:
        raise ValueError(f"Unsafe hotkey '{hotkey_str}': Bare non-function keys cannot be registered globally.")

    return modifiers, vk_code


class WinNativeEventFilter(QAbstractNativeEventFilter):
    """Filters native Windows messages to intercept WM_HOTKEY reliably."""

    def __init__(self, callback: Callable[[int], bool]):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        try:
            if sys.platform == "win32":
                evt = bytes(event_type) if hasattr(event_type, "data") else event_type
                if isinstance(evt, str):
                    evt = evt.encode("ascii", "ignore")

                # Qt 6 on Windows dispatches thread messages as windows_dispatcher_MSG
                if evt in (b"windows_dispatcher_MSG", b"windows_generic_MSG"):
                    if not message:
                        return False
                    ptr = int(message)
                    if ptr == 0:
                        return False
                    msg = wintypes.MSG.from_address(ptr)
                    if msg.message == WM_HOTKEY:
                        hotkey_id = int(msg.wParam)
                        if self.callback(hotkey_id):
                            return True  # Handled & consumed
        except KeyboardInterrupt:
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.quit()
            return False
        except BaseException:
            pass
        return False


class GlobalHotkeyManager(QObject):
    """Manages global hotkey registration, fallback handling, and native event filtering."""

    hotkey_triggered = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter: Optional[WinNativeEventFilter] = None
        self._registered_ids: Dict[int, str] = {}
        self._current_id = 100
        self._app = None
        self._active_hotkey: Optional[str] = None
        self._last_trigger_time = 0.0

    @property
    def active_hotkey(self) -> Optional[str]:
        return self._active_hotkey

    def start(self, q_app) -> None:
        """Installs the native event filter on the application."""
        self._app = q_app
        if sys.platform == "win32" and self._filter is None:
            self._filter = WinNativeEventFilter(self._on_native_hotkey)
            self._app.installNativeEventFilter(self._filter)

    def stop(self) -> None:
        """Unregisters all hotkeys and removes the native event filter cleanly."""
        self.unregister_all()
        if self._app and self._filter:
            try:
                self._app.removeNativeEventFilter(self._filter)
            except Exception:
                pass
            self._filter = None
        self._app = None

    def register_hotkey(self, hotkey_str: str) -> int:
        """Registers a global hotkey across Windows. Returns the ID, or -1 on failure."""
        if sys.platform != "win32":
            return -1

        try:
            modifiers, vk_code = parse_hotkey_string(hotkey_str)
        except ValueError as err:
            print(f"[Hotkey Error] {err}")
            return -1

        hotkey_id = self._current_id
        kernel32.SetLastError(ERROR_SUCCESS)
        success = user32.RegisterHotKey(None, hotkey_id, modifiers, vk_code)

        if not success and (modifiers & MOD_NOREPEAT):
            # Fallback retry without MOD_NOREPEAT (crucial on Windows with certain IMEs or keyboard layouts)
            success = user32.RegisterHotKey(None, hotkey_id, modifiers & ~MOD_NOREPEAT, vk_code)

        if success:
            self._current_id += 1
            self._registered_ids[hotkey_id] = hotkey_str
            self._active_hotkey = hotkey_str
            return hotkey_id

        err_code = kernel32.GetLastError()
        if err_code == ERROR_HOTKEY_ALREADY_REGISTERED:
            print(f"[Hotkey Conflict] Hotkey '{hotkey_str}' is already registered by another application.")
        elif err_code == ERROR_INVALID_PARAMETER:
            print(f"[Hotkey Error] Invalid parameters for hotkey '{hotkey_str}'.")
        else:
            print(f"[Hotkey Error] Failed to register '{hotkey_str}' (Win32 Error: {err_code}).")

        return -1

    def register_with_fallbacks(self, preferred: str, fallbacks: List[str]) -> Tuple[int, Optional[str]]:
        """Attempts to register the preferred hotkey; if taken, cycles through fallback list."""
        candidates = [preferred] + [fb for fb in fallbacks if fb.lower() != preferred.lower()]
        for candidate in candidates:
            hid = self.register_hotkey(candidate)
            if hid >= 0:
                return hid, candidate
        return -1, None

    def unregister_all(self) -> None:
        """Unregisters all active hotkeys cleanly."""
        if sys.platform == "win32":
            for hotkey_id in list(self._registered_ids.keys()):
                user32.UnregisterHotKey(None, hotkey_id)
            self._registered_ids.clear()
            self._active_hotkey = None

    def _on_native_hotkey(self, hotkey_id: int) -> bool:
        if hotkey_id in self._registered_ids:
            now = time.monotonic()
            if now - self._last_trigger_time >= 0.20:
                self._last_trigger_time = now
                self.hotkey_triggered.emit(hotkey_id)
            return True
        return False
