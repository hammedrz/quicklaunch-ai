"""Application Configuration with validation, atomic persistence, and multi-tier loading."""
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"

# Load .env file from project root or CWD
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)
else:
    load_dotenv()

AppMode = Literal["simple", "agent", "cli"]


def _get_app_dir() -> Path:
    """Returns the persistent OS-level application directory."""
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    app_dir = base / "QuickLaunchAI"
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return app_dir


def _validate_timeout(raw_val: str, default: float = 5.0) -> float:
    """Validates timeout string, enforcing bounds [0.5, 300.0] with graceful fallback."""
    try:
        val = float(raw_val)
        if 0.5 <= val <= 300.0:
            return val
        return default
    except (ValueError, TypeError):
        return default


def _validate_mode(raw_val: str, default: AppMode = "simple") -> AppMode:
    """Validates operational mode enum ('simple', 'agent', or 'cli')."""
    cleaned = (raw_val or "").strip().lower()
    if cleaned in ("simple", "agent", "cli"):
        return cleaned  # type: ignore
    return default


def _validate_hotkey(raw_val: str, default: str = "ctrl+space") -> str:
    """Ensures hotkey has at least one modifier and one key."""
    parts = [p.strip().lower() for p in (raw_val or "").replace("-", "+").split("+") if p.strip()]
    modifiers = {"alt", "menu", "ctrl", "control", "shift", "win", "windows", "super", "cmd"}
    has_mod = any(p in modifiers for p in parts)
    has_key = any(p not in modifiers for p in parts)
    if has_mod and has_key:
        return "+".join(parts)
    return default


@dataclass
class AppConfig:
    """Global configuration settings with validated types and fallback safety."""

    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip()
    )
    simple_model: str = field(
        default_factory=lambda: os.getenv("SIMPLE_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    )
    agent_model: str = field(
        default_factory=lambda: os.getenv("AGENT_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    )
    cli_model: str = field(
        default_factory=lambda: os.getenv("CLI_MODEL", "").strip()
    )
    default_mode: AppMode = field(
        default_factory=lambda: _validate_mode(os.getenv("DEFAULT_MODE", "simple"))
    )
    hotkey: str = field(
        default_factory=lambda: _validate_hotkey(os.getenv("LAUNCHER_HOTKEY", "ctrl+space"))
    )
    search_enabled: bool = field(
        default_factory=lambda: os.getenv("SEARCH_ENABLED", "true").strip().lower() in ("true", "1", "yes", "on")
    )
    sandbox_timeout_seconds: float = field(
        default_factory=lambda: _validate_timeout(os.getenv("SANDBOX_TIMEOUT", "5.0"))
    )

    # App Dimensions & Paths
    window_width: int = 860
    min_window_height: int = 64
    max_window_height: int = 760
    app_dir: Path = field(default_factory=_get_app_dir)

    def is_api_key_configured(self) -> bool:
        """Checks if a non-empty Gemini API key is configured."""
        return bool(self.gemini_api_key and len(self.gemini_api_key) > 8)

    def save_api_key(self, key: str) -> None:
        """Atomically persists the API key to .env and the APPDATA user config."""
        cleaned_key = re.sub(r"[\r\n\t]", "", key).strip()
        self.gemini_api_key = cleaned_key
        os.environ["GEMINI_API_KEY"] = cleaned_key

        # 1. Update Project .env atomically
        self._write_dotenv_key("GEMINI_API_KEY", cleaned_key, DOTENV_PATH)

        # 2. Persist to AppData user config for desktop safety
        user_env = self.app_dir / ".env"
        self._write_dotenv_key("GEMINI_API_KEY", cleaned_key, user_env)

    @staticmethod
    def _write_dotenv_key(var_name: str, value: str, target_file: Path) -> None:
        """Safely updates or adds a variable in a .env file using an atomic write."""
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            if target_file.exists():
                lines = target_file.read_text(encoding="utf-8").splitlines()

            pattern = re.compile(rf"^\s*(export\s+)?{re.escape(var_name)}\s*=", re.IGNORECASE)
            updated = False
            new_lines = []

            for line in lines:
                if pattern.match(line):
                    new_lines.append(f"{var_name}={value}")
                    updated = True
                else:
                    new_lines.append(line)

            if not updated:
                new_lines.append(f"{var_name}={value}")

            content = "\n".join(new_lines) + "\n"

            # Atomic file replacement
            temp_file = target_file.with_suffix(f".tmp.{os.getpid()}")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(target_file)
        except OSError as err:
            print(f"[Config Error] Failed to write to {target_file}: {err}", file=sys.stderr)


# Global singleton instance
config = AppConfig()
