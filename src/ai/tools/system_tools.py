"""System utility tools for QuickLaunch AI: Safe Math AST, System Diagnostics, Win32 Clipboard, and App Launcher."""
import ast
import functools
import math
import operator
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict

# ── 1. Safe AST-Based Math Calculator ────────────────────────────────

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

SAFE_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

def safe_pow(base: Any, exponent: Any) -> Any:
    """Safe exponentiation guarded against CPU and memory exhaustion."""
    if abs(base) > 10000 and exponent > 10:
        raise ValueError("Exponentiation base and exponent too large.")
    if abs(exponent) > 1000:
        raise ValueError("Exponent too large (maximum allowed exponent is 1000).")
    try:
        if isinstance(base, int) and isinstance(exponent, int) and exponent >= 0:
            return base ** exponent
        return math.pow(base, exponent)
    except OverflowError:
        raise ValueError("Result exceeds numeric limits (overflow).")

SAFE_FUNCTIONS: Dict[str, Any] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pi": math.pi,
    "e": math.e,
    "pow": safe_pow,
}


def _eval_ast_node(node: ast.AST) -> Any:
    """Recursively evaluates an AST node with strict type and node whitelisting."""
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Disallowed constant type: {type(node.value).__name__}")

    if isinstance(node, ast.Name):
        if node.id in SAFE_FUNCTIONS:
            val = SAFE_FUNCTIONS[node.id]
            if isinstance(val, (int, float)):
                return val
            raise ValueError(f"Function '{node.id}' must be called with arguments.")
        raise ValueError(f"Unknown variable or function: '{node.id}'")

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in SAFE_UNARY_OPERATORS:
            operand = _eval_ast_node(node.operand)
            return SAFE_UNARY_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            left = _eval_ast_node(node.left)
            right = _eval_ast_node(node.right)
            return safe_pow(left, right)

        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            left = _eval_ast_node(node.left)
            right = _eval_ast_node(node.right)
            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct mathematical function calls are permitted.")
        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise ValueError(f"Function '{func_name}' is not allowed.")
        fn = SAFE_FUNCTIONS[func_name]
        if not callable(fn):
            raise ValueError(f"'{func_name}' is a constant, not a function.")
        args = [_eval_ast_node(arg) for arg in node.args]
        return fn(*args)

    raise ValueError(f"Syntax element not allowed in calculations: {type(node).__name__}")


def calculate(expression: str) -> str:
    """Evaluates a mathematical expression safely using deterministic AST parsing.

    Args:
        expression: A mathematical formula, e.g. "sqrt(144) + 2^3" or "sin(pi/2) * 50".

    Returns:
        The computed result as a string or an error description.
    """
    if not expression or not expression.strip():
        return "Calculation Error: Empty expression."

    sanitized = expression.replace("^", "**").strip()
    if len(sanitized) > 256:
        return "Calculation Error: Expression exceeds maximum length (256 characters)."

    try:
        parsed = ast.parse(sanitized, mode="eval")
        result = _eval_ast_node(parsed)
        return str(result)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as exc:
        return f"Calculation Error: {exc}"
    except Exception as exc:
        return f"Calculation Error: Invalid expression ({exc})"


# ── 2. System Diagnostics ──────────────────────────────────────────

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
    kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002


@functools.lru_cache(maxsize=1)
def _get_static_platform_info() -> str:
    """Caches immutable OS and CPU hardware platform details."""
    os_info = f"{platform.system()} {platform.release()} ({platform.version()})"
    cpu_arch = platform.machine()
    processor = platform.processor()
    return f"OS: {os_info}\nArchitecture: {cpu_arch}\nProcessor: {processor}"


def get_system_info() -> str:
    """Retrieves basic host system diagnostics including OS, CPU, memory, and disk space."""
    try:
        system_drive = os.environ.get("SystemDrive", "C:") + os.sep
        total, used, free = shutil.disk_usage(system_drive)
        total_gb = round(total / (1024**3), 2)
        free_gb = round(free / (1024**3), 2)
        used_gb = round(used / (1024**3), 2)

        platform_str = _get_static_platform_info()

        memory_str = "Unavailable"
        if sys.platform == "win32":
            try:
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_ram_gb = round(stat.ullTotalPhys / (1024**3), 2)
                    avail_ram_gb = round(stat.ullAvailPhys / (1024**3), 2)
                    used_ram_gb = round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3), 2)
                    memory_str = f"{used_ram_gb} GB used / {total_ram_gb} GB total ({stat.dwMemoryLoad}% load, {avail_ram_gb} GB free)"
            except Exception:
                pass

        return (
            f"{platform_str}\n"
            f"RAM: {memory_str}\n"
            f"Primary Disk: {used_gb} GB used / {total_gb} GB total ({free_gb} GB free on {system_drive})"
        )
    except Exception as exc:
        return f"Error retrieving system info: {exc}"


# ── 3. Safe 64-bit Windows Clipboard Tools ──────────────────────────

def get_clipboard() -> str:
    """Reads the current plain text contents from the Windows clipboard."""
    if sys.platform != "win32":
        return "Clipboard access is only supported on Windows."

    try:
        opened = False
        for _ in range(5):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.015)

        if not opened:
            return "Unable to access clipboard."

        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return "(Clipboard is empty or contains non-text data)"

            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return "Unable to lock clipboard memory."
            try:
                text = ctypes.c_wchar_p(ptr).value
                return text if text else "(Empty text)"
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        return f"Error reading clipboard: {exc}"


def set_clipboard(text: str) -> str:
    """Copies the provided text into the Windows clipboard safely."""
    if sys.platform != "win32":
        return "Clipboard access is only supported on Windows."

    try:
        data = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_mem:
            return "Memory allocation failed."

        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            kernel32.GlobalFree(h_mem)
            return "GlobalLock failed."

        try:
            ctypes.memmove(ptr, data, len(data))
        finally:
            kernel32.GlobalUnlock(h_mem)

        opened = False
        for _ in range(5):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.015)

        if not opened:
            kernel32.GlobalFree(h_mem)
            return "Failed to open clipboard."

        try:
            user32.EmptyClipboard()
            res = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            if not res:
                kernel32.GlobalFree(h_mem)
                return "SetClipboardData failed."
            return f"Successfully copied {len(text)} characters to clipboard."
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        return f"Error setting clipboard: {exc}"


# ── 4. Safe Application & URL Launcher ──────────────────────────────

SAFE_WINDOWS_APPS = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "mspaint": "mspaint.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "msedge": "msedge.exe",
    "code": "code.cmd",
}

DISALLOWED_EXTENSIONS = {
    ".bat", ".cmd", ".ps1", ".vbs", ".js", ".hta", ".reg", ".scr",
    ".pif", ".cpl", ".wsf", ".msi", ".com",
}

DISALLOWED_PROTOCOLS = {
    "ms-msdt", "search-ms", "shell", "file", "diskpart", "wsf"
}


def launch_app_or_url(target: str) -> str:
    """Launches a verified Windows application, safe file, or approved web URL.

    Args:
        target: A web URL (https://...) or recognized application name (e.g. 'calc', 'notepad').

    Returns:
        Confirmation or safety rejection message.
    """
    target = target.strip()
    if not target:
        return "Error: Target is empty."

    try:
        if target.startswith("http://") or target.startswith("https://"):
            parsed = urllib.parse.urlsplit(target)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return f"Error: Invalid or unparseable URL '{target}'."
            if any(ord(c) < 32 for c in target):
                return "Error: URL contains invalid control characters."

            import webbrowser
            webbrowser.open(target)
            return f"Opened URL in browser: {target}"

        if ":" in target and not (len(target) > 2 and target[1] == ":" and target[2] in ("\\", "/")):
            scheme = target.split(":", 1)[0].lower()
            if scheme in DISALLOWED_PROTOCOLS:
                return f"Error: Protocol scheme '{scheme}:' is blocked for security."

        target_lower = target.lower()
        if target_lower in SAFE_WINDOWS_APPS:
            app_exec = SAFE_WINDOWS_APPS[target_lower]
            if sys.platform == "win32":
                subprocess.Popen([app_exec], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen([app_exec])
            return f"Launched application: {target}"

        target_path = Path(target)
        if target_path.suffix.lower() in DISALLOWED_EXTENSIONS:
            return f"Security Error: Executable scripts of type '{target_path.suffix}' are blocked from execution."

        if target_path.exists() and target_path.is_file():
            if sys.platform == "win32":
                os.startfile(str(target_path.resolve()))
                return f"Opened file: {target_path.name}"
            else:
                subprocess.Popen(["xdg-open", str(target_path.resolve())])
                return f"Opened file: {target_path.name}"

        return f"Error: Target '{target}' is neither an approved application, supported file, nor valid web URL."

    except Exception as exc:
        return f"Failed to launch '{target}': {exc}"
