"""Unit tests for state_manager (window state persistence and query history)."""
from pathlib import Path
from unittest.mock import patch
import pytest
from PySide6.QtCore import QPoint

from src.state_manager import StateManager


@pytest.fixture
def temp_state_mgr(tmp_path):
    mgr = StateManager()
    mgr.state_file = tmp_path / "state.json"
    mgr.history_file = tmp_path / "history.json"
    return mgr


def test_save_and_load_window_state(temp_state_mgr):
    pos = QPoint(300, 200)
    temp_state_mgr.save_window_state(pos, True, "agent")

    loaded_pos, user_moved, mode = temp_state_mgr.load_window_state()
    assert user_moved is True
    assert mode == "agent"
    assert loaded_pos is not None
    assert loaded_pos.x() == 300
    assert loaded_pos.y() == 200


def test_load_window_state_default_when_empty(temp_state_mgr):
    loaded_pos, user_moved, mode = temp_state_mgr.load_window_state()
    assert loaded_pos is None
    assert user_moved is False
    assert mode in ("simple", "agent", "cli")


def test_query_history_add_and_deduplicate(temp_state_mgr):
    temp_state_mgr.add_history("first query")
    temp_state_mgr.add_history("second query")
    temp_state_mgr.add_history("first query")  # Promote to top

    history = temp_state_mgr.load_history()
    assert history == ["first query", "second query"]


def test_query_history_max_limit(temp_state_mgr):
    temp_state_mgr.max_history = 5
    for i in range(10):
        temp_state_mgr.add_history(f"query {i}")

    history = temp_state_mgr.load_history()
    assert len(history) == 5
    assert history[0] == "query 9"


def test_clear_history(temp_state_mgr):
    temp_state_mgr.add_history("test query")
    assert len(temp_state_mgr.load_history()) == 1

    temp_state_mgr.clear_history()
    assert len(temp_state_mgr.load_history()) == 0
