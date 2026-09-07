"""Windows Startup Apps Manager for QuickLaunch AI.

Registers the application in Windows Task Manager's 'Startup apps' tab
using a formatted Windows shortcut (.lnk) in the user's Startup folder.
This guarantees that Task Manager displays 'QuickLaunch AI' (rather than 'python'
or 'pythonw') and keeps status synchronized with Task Manager's enable/disable state.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("QuickLaunch.Autostart")

APP_NAME = "QuickLaunch AI"
SHORTCUT_FILENAME = f"{APP_NAME}.lnk"
APPROVED_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"


def is_windows() -> bool:
    """Returns True if the current runtime platform is Windows."""
    return sys.platform == "win32"


def get_startup_folder() -> Path:
    """Returns the Windows User Startup folder path (%APPDATA%\\...\\Startup)."""
    appdata = os.getenv("APPDATA")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def get_shortcut_path() -> Path:
    """Returns the full path to the QuickLaunch AI startup shortcut."""
    return get_startup_folder() / SHORTCUT_FILENAME


def is_autostart_enabled() -> bool:
    """Checks if QuickLaunch AI is registered and NOT disabled in Task Manager.
    
    Inspects both the presence of the .lnk file in the user's Startup folder
    and the Windows Registry 'StartupApproved\\StartupFolder' key where Task Manager
    stores user-toggled enabled/disabled states.
    """
    if not is_windows():
        return False

    shortcut = get_shortcut_path()
    if not shortcut.exists():
        return False

    # Check if user disabled it inside Task Manager's Startup Apps tab
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, shortcut.name)
            # Binary data: byte 0 == 0x03 (or 0x01) means user disabled it in Task Manager
            if isinstance(val, (bytes, bytearray)) and len(val) > 0:
                if val[0] in (0x03, 0x01):
                    return False
    except (FileNotFoundError, OSError):
        # Entry not present in StartupApproved means default enabled
        pass

    return True


def enable_autostart() -> Tuple[bool, str]:
    """Registers QuickLaunch AI in Task Manager's Startup apps section via a Windows shortcut."""
    if not is_windows():
        return False, "Startup registration is only supported on Windows."

    shortcut_path = get_shortcut_path()
    project_root = Path(__file__).resolve().parent.parent

    if getattr(sys, "frozen", False):
        # Compiled binary (e.g. PyInstaller)
        target_path = Path(sys.executable).resolve()
        args = "--autostart"
        work_dir = target_path.parent
    else:
        # Development mode: use pythonw.exe to prevent terminal window popping up
        py_exe = Path(sys.executable)
        if py_exe.stem.lower() == "python":
            pythonw = py_exe.with_name("pythonw.exe")
            if pythonw.exists():
                py_exe = pythonw
        target_path = py_exe.resolve()
        main_py = (project_root / "main.py").resolve()
        args = f'"{main_py}" --autostart'
        work_dir = project_root

    # PowerShell script to create or update the .lnk shortcut
    ps_command = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{target_path}"
    $Shortcut.Arguments = '{args}'
    $Shortcut.WorkingDirectory = "{work_dir}"
    $Shortcut.Description = "QuickLaunch AI Launcher"
    $Shortcut.Save()
    """

    try:
        startup_dir = shortcut_path.parent
        startup_dir.mkdir(parents=True, exist_ok=True)

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_command],
            check=True,
            capture_output=True,
            creationflags=creationflags,
        )
        logger.info("Created Startup apps shortcut at: %s", shortcut_path)

        # Reset Task Manager disabled state in StartupApproved if it was previously disabled
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                # 0x02 indicates enabled by user
                winreg.SetValueEx(key, shortcut_path.name, 0, winreg.REG_BINARY, b"\x02" + b"\x00" * 11)
        except (FileNotFoundError, OSError):
            pass

        return True, "Enabled"
    except Exception as err:
        logger.error("Failed to create startup shortcut: %s", err)
        return False, str(err)


def disable_autostart() -> Tuple[bool, str]:
    """Removes QuickLaunch AI from Task Manager's Startup apps section."""
    shortcut_path = get_shortcut_path()
    try:
        if shortcut_path.exists():
            shortcut_path.unlink()
            logger.info("Deleted Startup apps shortcut: %s", shortcut_path)
        return True, "Disabled"
    except OSError as err:
        logger.error("Failed to delete startup shortcut: %s", err)
        return False, str(err)


def toggle_autostart(enable: bool) -> Tuple[bool, str]:
    """Toggles autostart on or off."""
    return enable_autostart() if enable else disable_autostart()
