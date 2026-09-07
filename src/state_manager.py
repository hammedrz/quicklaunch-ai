"""Persistent state and query history manager for QuickLaunch AI."""
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from .config import config


class StateManager:
    """Handles persistent storage of window coordinates, mode, and query history."""

    def __init__(self):
        self.state_file: Path = config.app_dir / "state.json"
        self.history_file: Path = config.app_dir / "history.json"
        self.max_history: int = 200

    # ── State Persistence (Window & Mode) ──────────────────────────────
    def save_window_state(self, pos: QPoint, user_moved: bool, mode: str) -> None:
        """Saves window coordinates, moved flag, mode, and model preferences to state.json."""
        data = {
            "x": pos.x(),
            "y": pos.y(),
            "user_moved": user_moved,
            "mode": mode,
            "simple_model": config.simple_model,
            "agent_model": config.agent_model,
            "cli_model": config.cli_model,
        }
        self._atomic_json_write(self.state_file, data)

    def load_window_state(self) -> Tuple[Optional[QPoint], bool, str]:
        """Loads window state, verifying coordinates intersect an active monitor."""
        if not self.state_file.exists():
            return None, False, config.default_mode

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            x = data.get("x")
            y = data.get("y")
            user_moved = data.get("user_moved", False)
            mode = data.get("mode", config.default_mode)

            # Restore model selections if stored
            if data.get("simple_model"):
                config.simple_model = data["simple_model"]
            if data.get("agent_model"):
                config.agent_model = data["agent_model"]
            if "cli_model" in data:
                config.cli_model = data["cli_model"]

            if x is not None and y is not None and user_moved:
                target_point = QPoint(x, y)
                if self._is_point_on_any_screen(target_point):
                    return target_point, True, mode
                return None, False, mode

            return None, False, mode
        except (json.JSONDecodeError, OSError) as err:
            print(f"[State Warning] Could not load window state: {err}", file=sys.stderr)
            return None, False, config.default_mode

    @staticmethod
    def _is_point_on_any_screen(point: QPoint) -> bool:
        """Checks if the point intersects any currently active display."""
        test_rect = QRect(point.x(), point.y(), 100, 50)
        app = QApplication.instance()
        if not app:
            return True
        for screen in QApplication.screens():
            if screen.availableGeometry().intersects(test_rect):
                return True
        return False

    # ── Query History ──────────────────────────────────────────────────
    def load_history(self) -> List[str]:
        """Loads query history from disk (most recent first)."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                return history if isinstance(history, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def add_history(self, query: str) -> List[str]:
        """Adds query to history with deduplication and bounded size, then saves."""
        cleaned = query.strip()
        if not cleaned:
            return self.load_history()

        history = self.load_history()
        if cleaned in history:
            history.remove(cleaned)

        history.insert(0, cleaned)
        history = history[: self.max_history]

        self._atomic_json_write(self.history_file, history)
        return history

    def clear_history(self) -> None:
        """Clears query history from disk."""
        self._atomic_json_write(self.history_file, [])

    # ── Helper ────────────────────────────────────────────────────────
    @staticmethod
    def _atomic_json_write(target_file: Path, payload: dict | list) -> None:
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = target_file.with_suffix(f".tmp.{os.getpid()}")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(target_file)
        except OSError as err:
            print(f"[State Error] Failed to write {target_file}: {err}", file=sys.stderr)


state_manager = StateManager()
