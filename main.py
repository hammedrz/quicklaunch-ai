"""QuickLaunch AI - Application Entry Point."""
import atexit
import ctypes
from ctypes import wintypes
import os
import signal
import sys

from PySide6.QtCore import QMetaObject, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.ai.model_registry import model_registry
from src.config import config
from src.hotkey import GlobalHotkeyManager
from src.state_manager import state_manager
from src.ui.launcher_window import LauncherWindow
from src.ui.tray import SystemTrayManager


def set_windows_app_user_model_id():
    """Sets the Application User Model ID for Windows toast notifications & taskbar grouping."""
    if sys.platform == "win32":
        try:
            my_appid = "QuickLaunchAI.Launcher.Desktop.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_appid)
        except Exception as e:
            print(f"[Warning] Failed to set AppUserModelID: {e}")


def check_single_instance():
    """Ensures only one instance of QuickLaunch AI runs at a time.
    If another instance is running, brings it to foreground and exits cleanly.
    """
    if sys.platform != "win32":
        return None

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    ERROR_ALREADY_EXISTS = 183

    mutex = kernel32.CreateMutexW(None, False, "Local\\QuickLaunchAI_App_Instance_Mutex")
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if mutex:
            kernel32.CloseHandle(mutex)
        # Find existing window and summon it
        hwnd = user32.FindWindowW(None, "QuickLaunch AI")
        if hwnd:
            user32.ShowWindow(hwnd, 5)  # SW_SHOW
            user32.SetForegroundWindow(hwnd)
        print("[Info] QuickLaunch AI is already running. Brought existing instance to foreground.")
        sys.exit(0)

    return mutex


def main():
    # Enforce single instance to prevent duplicate processes from hijacking global hotkeys
    app_mutex = check_single_instance()

    # Set explicit AppUserModelID before QApplication initialization
    set_windows_app_user_model_id()

    # PassThrough rounding policy for smooth High-DPI rendering
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("QuickLaunch AI")
    app.setQuitOnLastWindowClosed(False)  # Run persistently in system tray
    app.setFont(QFont("Segoe UI", 10))

    # Create launcher window
    launcher = LauncherWindow()

    # Setup global hotkey with ordered fallback candidates
    hotkey_manager = GlobalHotkeyManager()
    hotkey_manager.start(app)

    fallbacks = ["ctrl+shift+space", "alt+space", "win+shift+space", "ctrl+alt+space"]
    hotkey_id, active_hotkey = hotkey_manager.register_with_fallbacks(
        preferred=config.hotkey,
        fallbacks=fallbacks,
    )

    def on_hotkey(hid: int):
        if launcher.isVisible() and launcher.isActiveWindow():
            launcher.dismiss()
        else:
            launcher.summon()

    hotkey_manager.hotkey_triggered.connect(on_hotkey)

    # Initialize System Tray
    tray = SystemTrayManager(
        on_show=launcher.summon,
        on_toggle_mode=lambda: launcher.search_bar.mode_pill.toggle(),
        on_clear=lambda: launcher._clear_all(),
        on_recenter=launcher.recenter,
        on_quit=lambda: app.quit(),
        on_settings=launcher.open_settings,
        on_clear_history=state_manager.clear_history,
        hotkey_str=active_hotkey or "",
    )
    tray.show()

    # Trigger background model discovery from Gemini API if key is configured
    if config.is_api_key_configured():
        model_registry.refresh_async()

    # Clean shutdown handler (guarantees no ghost tray icons or dangling event filters)
    _shutdown_done = False
    _console_handler_ref = None

    def clean_shutdown():
        nonlocal _shutdown_done, _console_handler_ref
        if _shutdown_done:
            return
        _shutdown_done = True

        if sys.platform == "win32" and _console_handler_ref:
            try:
                ctypes.windll.kernel32.SetConsoleCtrlHandler(_console_handler_ref, False)
            except Exception:
                pass
            _console_handler_ref = None

        if launcher._worker and launcher._worker.isRunning():
            launcher._worker.cancel()
            launcher._worker.wait(400)
        hotkey_manager.stop()
        tray.cleanup()
        if app_mutex and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(app_mutex)
            except Exception:
                pass

    app.aboutToQuit.connect(clean_shutdown)
    atexit.register(clean_shutdown)

    def request_quit():
        """Gracefully requests application shutdown on the Qt main loop."""
        QMetaObject.invokeMethod(app, "quit", Qt.ConnectionType.QueuedConnection)

    # Clean Ctrl+C (SIGINT) & SIGTERM handling across platforms
    _interrupt_count = 0

    def sig_handler(sig, frame):
        nonlocal _interrupt_count
        _interrupt_count += 1
        if _interrupt_count == 1:
            request_quit()
        else:
            clean_shutdown()
            os._exit(0)

    try:
        signal.signal(signal.SIGINT, sig_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, sig_handler)
    except Exception:
        pass

    # On Windows, intercept console control events before Python's default handler raises KeyboardInterrupt
    if sys.platform == "win32":
        CTRL_C_EVENT = 0
        CTRL_BREAK_EVENT = 1
        CTRL_CLOSE_EVENT = 2

        PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def win_console_ctrl_handler(ctrl_type: int) -> bool:
            nonlocal _interrupt_count
            if ctrl_type in (CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT):
                _interrupt_count += 1
                if _interrupt_count == 1:
                    request_quit()
                    return True
                else:
                    clean_shutdown()
                    os._exit(0)
            return False

        _console_handler_ref = PHANDLER_ROUTINE(win_console_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_console_handler_ref, True)

    # Periodic timer to allow Python's signal handler to process signals promptly
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(250)

    # Display startup notification after Explorer shell registers the tray icon
    def show_startup_notice():
        if active_hotkey:
            pretty_key = active_hotkey.replace("+", " + ").title()
            if active_hotkey.lower() != config.hotkey.lower():
                tray.show_notification(
                    "QuickLaunch AI (Fallback Hotkey)",
                    f"'{config.hotkey}' was taken by another app. "
                    f"Press {pretty_key} to summon.",
                    is_warning=True,
                )
            else:
                tray.show_notification(
                    "QuickLaunch AI is running",
                    f"Press {pretty_key} to summon / dismiss.",
                )
        else:
            tray.show_notification(
                "QuickLaunch AI Warning",
                "Could not register any global hotkeys. Click the tray icon to open.",
                is_warning=True,
            )

    QTimer.singleShot(300, show_startup_notice)

    # Set default mode from config or saved state
    initial_mode = getattr(launcher, "_saved_mode", config.default_mode)
    launcher.search_bar.set_mode(initial_mode)
    launcher.status_bar.set_mode(initial_mode)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
