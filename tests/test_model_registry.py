"""Tests for dynamic model discovery, free-tier filtering, and caching."""
import json
import pytest
from unittest.mock import MagicMock, patch

from src.ai.model_registry import (
    BLOCKED_MODELS,
    DEFAULT_FREE_TIER_MODELS,
    EXCLUDED_KEYWORDS,
    ModelRegistry,
    _format_model_badge,
    _model_sort_key,
)
from src.ui.search_bar import ModelSelector
from src.ui.api_key_dialog import ApiKeyDialog


def test_default_models_include_gemma_and_flash():
    """Verify default fallback models contain gemma-4-31b-it and gemini flash models."""
    model_ids = [m[0] for m in DEFAULT_FREE_TIER_MODELS]
    assert "gemma-4-31b-it" in model_ids
    assert "gemma-4-26b-a4b-it" in model_ids
    assert "gemini-2.5-flash" in model_ids
    assert "gemini-3.5-flash" in model_ids
    assert "gemini-3.7-flash" in model_ids


def test_format_model_badge():
    """Verify intuitive badge assignment."""
    assert "💎" in _format_model_badge("gemma-4-31b-it", "Gemma 4 31B IT")
    assert "⚡" in _format_model_badge("gemini-2.5-flash", "Gemini 2.5 Flash")
    assert "🚀" in _format_model_badge("gemini-3.5-flash", "Gemini 3.5 Flash")
    assert "🧠" in _format_model_badge("gemini-3.7-flash", "Gemini 3.7 Flash")
    assert "🔬" in _format_model_badge("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview")


def test_model_sort_key():
    """Verify sort key priorities."""
    k_flash = _model_sort_key(("gemini-2.5-flash", "label"))
    k_gemma = _model_sort_key(("gemma-4-31b-it", "label"))
    assert k_flash < k_gemma


def test_filter_api_models_free_tier(tmp_path):
    """Verify filtering retains free tier & gemma models while filtering out audio/image/robotics."""
    class FakeModel:
        def __init__(self, name, display_name, actions):
            self.name = name
            self.display_name = display_name
            self.supported_actions = actions

    fake_raw = [
        FakeModel("models/gemini-2.5-flash", "Gemini 2.5 Flash", ["generateContent"]),
        FakeModel("models/gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite", ["generateContent"]),
        FakeModel("models/gemma-4-31b-it", "Gemma 4 31B IT", ["generateContent"]),
        FakeModel("models/gemma-4-26b-a4b-it", "Gemma 4 26B A4B IT", ["generateContent"]),
        FakeModel("models/gemini-3.5-flash", "Gemini 3.5 Flash", ["generateContent"]),
        FakeModel("models/gemini-2.5-pro", "Gemini 2.5 Pro", ["generateContent"]),  # Blocked (404)
        FakeModel("models/gemini-2.5-flash-preview-tts", "Gemini TTS", ["generateContent"]),  # Excluded audio
        FakeModel("models/gemini-2.5-flash-image", "Nano Banana", ["generateContent"]),  # Excluded image
        FakeModel("models/lyria-3-pro-preview", "Lyria 3", ["generateContent"]),  # Excluded music
        FakeModel("models/gemini-robotics-er-2", "Robotics", ["generateContent"]),  # Excluded robotics
        FakeModel("models/gemini-embedding-2", "Embedding", ["embedContent"]),  # No generateContent
    ]

    registry = ModelRegistry()
    registry.cache_file = tmp_path / "models_cache.json"

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.list.return_value = fake_raw
        mock_client_cls.return_value = mock_client

        results = registry.fetch_models_from_api(api_key="fake-key-12345")
        result_ids = [r[0] for r in results]

        # Valid Free Tier Models
        assert "gemini-2.5-flash" in result_ids
        assert "gemini-2.5-flash-lite" in result_ids
        assert "gemma-4-31b-it" in result_ids
        assert "gemma-4-26b-a4b-it" in result_ids
        assert "gemini-3.5-flash" in result_ids

        # Excluded Models
        assert "gemini-2.5-pro" not in result_ids
        assert "gemini-2.5-flash-preview-tts" not in result_ids
        assert "gemini-2.5-flash-image" not in result_ids
        assert "lyria-3-pro-preview" not in result_ids
        assert "gemini-robotics-er-2" not in result_ids
        assert "gemini-embedding-2" not in result_ids

        # Verify cached to disk
        assert registry.cache_file.exists()
        with open(registry.cache_file, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
            disk_ids = [item[0] for item in disk_data]
            assert "gemma-4-31b-it" in disk_ids


def test_get_models_modes():
    """Verify mode formatting in get_models."""
    registry = ModelRegistry()
    simple_models = registry.get_models("simple")
    cli_models = registry.get_models("cli")

    assert cli_models[0][0] == ""
    assert "Default" in cli_models[0][1]
    assert len(cli_models) == len(simple_models) + 1


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_model_selector_ui_integration(qapp):
    """Verify ModelSelector uses dynamic model registry and renders labels properly."""
    selector = ModelSelector()

    selector.set_mode("simple")
    active = selector._get_active_model()
    assert selector.text().endswith("▾")

    # Change to gemma-4-31b-it
    selector._select_model("gemma-4-31b-it")
    assert "gemma-4-31b" in selector.text()


def test_api_key_dialog_model_population(qapp):
    """Verify ApiKeyDialog populates combos with free tier models including gemma-4-31b-it."""
    dialog = ApiKeyDialog()

    items = [dialog.simple_combo.itemData(i) for i in range(dialog.simple_combo.count())]
    assert "gemma-4-31b-it" in items
    assert "gemini-2.5-flash" in items
