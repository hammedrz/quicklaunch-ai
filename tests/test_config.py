"""Tests for application configuration."""
import os
import pytest
from src.config import AppConfig


def test_default_mode_is_simple():
    cfg = AppConfig()
    assert cfg.default_mode in ("simple", "agent")


def test_default_search_enabled():
    cfg = AppConfig()
    # Search grounding is disabled by default to protect free-tier API quotas
    assert cfg.search_enabled is False


def test_sandbox_timeout_default():
    cfg = AppConfig()
    assert cfg.sandbox_timeout_seconds == 5.0


def test_is_api_key_configured_empty():
    cfg = AppConfig(gemini_api_key="")
    assert cfg.is_api_key_configured() is False


def test_is_api_key_configured_present():
    cfg = AppConfig(gemini_api_key="test-key-123")
    assert cfg.is_api_key_configured() is True


def test_window_dimensions():
    cfg = AppConfig()
    assert cfg.window_width == 860
    assert cfg.min_window_height == 64
    assert cfg.max_window_height == 760

