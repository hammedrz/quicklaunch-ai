"""Dynamic model discovery, filtering, and caching for QuickLaunch AI."""
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from ..config import config

logger = logging.getLogger("QuickLaunch.ModelRegistry")

# Default curated free-tier models (fallback when offline or before initial sync)
DEFAULT_FREE_TIER_MODELS: List[Tuple[str, str]] = [
    ("gemini-3.1-flash-lite", "⚡ gemini-3.1-flash-lite (Fast • Default)"),
    ("gemini-2.5-flash", "⚡ gemini-2.5-flash (Fast)"),
    ("gemini-2.5-flash-lite", "⚡ gemini-2.5-flash-lite (Ultra Fast)"),
    ("gemini-3.5-flash", "🚀 gemini-3.5-flash (Next-Gen Flash)"),
    ("gemini-3.5-flash-lite", "🚀 gemini-3.5-flash-lite (Next-Gen Lite)"),
    ("gemini-3.7-flash", "🧠 gemini-3.7-flash (Advanced Reasoning)"),
    ("gemma-4-31b-it", "💎 gemma-4-31b-it (Google Open 31B)"),
    ("gemma-4-26b-a4b-it", "💎 gemma-4-26b-a4b-it (Google Open 26B MoE)"),
    ("gemini-3.1-pro-preview", "🔬 gemini-3.1-pro-preview (Pro Preview)"),
]

# Non-conversational or paid-only special capability keywords to exclude
EXCLUDED_KEYWORDS = [
    "tts",
    "transcribe",
    "audio",
    "live-translate",
    "image",
    "banana",
    "veo",
    "lyria",
    "robotics",
    "computer-use",
    "deep-research",
    "antigravity-preview",
    "customtools",
    "aqa",
    "embedding",
    "omni",
]

# Models that are retired/deprecated and return 404 from API
BLOCKED_MODELS = {
    "gemini-2.5-pro",
    "gemini-pro-latest",
}


def _format_model_badge(model_id: str, display_name: str) -> str:
    """Generates an intuitive emoji badge and clean label for the model."""
    clean_disp = display_name.strip() if display_name else model_id

    if model_id.startswith("gemma"):
        return f"💎 {model_id} ({clean_disp})"
    elif "3.7" in model_id:
        return f"🧠 {model_id} ({clean_disp})"
    elif any(v in model_id for v in ("3.5", "3.6", "3.8")):
        return f"🚀 {model_id} ({clean_disp})"
    elif "pro" in model_id:
        return f"🔬 {model_id} ({clean_disp})"
    else:
        return f"⚡ {model_id} ({clean_disp})"


def _model_sort_key(item: Tuple[str, str]) -> int:
    """Sort priority: Flash standard first, then Flash-Lite, then 3.x Flash, then Gemma, then Pro."""
    model_id = item[0].lower()
    if model_id == "gemini-3.1-flash-lite":
        return 0
    if model_id == "gemini-2.5-flash":
        return 1
    if model_id == "gemini-2.5-flash-lite":
        return 2
    if model_id == "gemini-3.5-flash":
        return 3
    if model_id == "gemini-3.5-flash-lite":
        return 4
    if model_id == "gemini-3.7-flash":
        return 5
    if model_id == "gemma-4-31b-it":
        return 6
    if model_id == "gemma-4-26b-a4b-it":
        return 7
    if "flash-lite" in model_id:
        return 10
    if "flash" in model_id:
        return 20
    if "gemma" in model_id:
        return 30
    if "pro" in model_id:
        return 40
    return 50


class ModelRegistry(QObject):
    """Manages dynamic discovery, filtering, and caching of Gemini API models."""

    models_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache_file: Path = config.app_dir / "models_cache.json"
        self._cached_models: List[Tuple[str, str]] = self._load_cache() or list(DEFAULT_FREE_TIER_MODELS)
        self._is_refreshing: bool = False

    def _load_cache(self) -> Optional[List[Tuple[str, str]]]:
        """Loads models from disk cache if present and valid."""
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return [(item[0], item[1]) for item in data if isinstance(item, (list, tuple)) and len(item) >= 2]
        except Exception as err:
            logger.warning(f"Failed to read models cache: {err}")
        return None

    def _save_cache(self, models: List[Tuple[str, str]]) -> None:
        """Atomically saves models to disk cache."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_file.with_suffix(f".tmp.{os.getpid()}")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(models, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(self.cache_file)
        except Exception as err:
            logger.warning(f"Failed to write models cache: {err}")

    def get_models(self, mode: str = "simple") -> List[Tuple[str, str]]:
        """Returns the available free-tier models for the requested operational mode."""
        base_models = list(self._cached_models)
        if mode == "cli":
            return [("", "🚀 Default (AGY Engine Default)")] + base_models
        return base_models

    def fetch_models_from_api(self, api_key: Optional[str] = None) -> List[Tuple[str, str]]:
        """Synchronously queries Google GenAI client.models.list() and filters for free-tier models."""
        key = (api_key or config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        if not key:
            return list(DEFAULT_FREE_TIER_MODELS)

        try:
            from google import genai

            client = genai.Client(api_key=key)
            api_models = client.models.list()
        except Exception as err:
            logger.error(f"Failed to fetch models from Gemini API: {err}")
            return list(self._cached_models)

        filtered: List[Tuple[str, str]] = []
        seen_ids = set()

        for m in api_models:
            raw_id = (getattr(m, "name", "") or "").removeprefix("models/").strip()
            if not raw_id or raw_id in seen_ids or raw_id in BLOCKED_MODELS:
                continue

            actions = getattr(m, "supported_actions", []) or []
            if "generateContent" not in actions:
                continue

            low_id = raw_id.lower()
            if any(kw in low_id for kw in EXCLUDED_KEYWORDS):
                continue

            # Check Free Tier eligibility:
            # 1. Gemini Flash models (e.g. gemini-2.5-flash, gemini-3.5-flash, gemini-3.7-flash, gemini-flash-latest)
            # 2. Gemma open models (e.g. gemma-4-31b-it, gemma-4-26b-a4b-it)
            # 3. Gemini Pro preview models with free tier access
            is_gemini_flash = "flash" in low_id and "gemini" in low_id
            is_gemma = low_id.startswith("gemma")
            is_pro_preview = low_id in ("gemini-3.1-pro-preview",)

            if is_gemini_flash or is_gemma or is_pro_preview:
                display_name = getattr(m, "display_name", "") or raw_id
                badge = _format_model_badge(raw_id, display_name)
                filtered.append((raw_id, badge))
                seen_ids.add(raw_id)

        # Ensure gemma-4-31b-it is always available even if API pagination had an issue
        if "gemma-4-31b-it" not in seen_ids:
            filtered.append(("gemma-4-31b-it", "💎 gemma-4-31b-it (Gemma 4 31B IT)"))

        # Sort by logical priority
        filtered.sort(key=_model_sort_key)

        if filtered:
            self._cached_models = filtered
            self._save_cache(filtered)
            return filtered

        return list(self._cached_models)

    def refresh_async(self, callback: Optional[Callable[[List[Tuple[str, str]]], None]] = None) -> None:
        """Asynchronously refreshes the model list in a background thread."""
        if self._is_refreshing:
            return

        self._is_refreshing = True

        def _worker():
            try:
                models = self.fetch_models_from_api()
            except Exception as err:
                logger.error(f"Background model refresh error: {err}")
                models = list(self._cached_models)
            finally:
                self._is_refreshing = False

            if callback:
                try:
                    callback(models)
                except Exception:
                    pass
            self.models_updated.emit()

        thread = threading.Thread(target=_worker, name="ModelRegistryRefreshThread", daemon=True)
        thread.start()


model_registry = ModelRegistry()
