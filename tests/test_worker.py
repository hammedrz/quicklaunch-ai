"""Tests for AgentWorker QThread and async event loop execution."""
from unittest.mock import AsyncMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from src.worker import AgentWorker


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_worker_simple_mode_execution(qapp):
    """Verify worker execution in simple mode emits chunks, status, sources, and finished."""
    worker = AgentWorker(prompt="Quick test", mode="simple")

    chunks = []
    statuses = []
    sources = []
    finished = []

    worker.sig_chunk.connect(chunks.append)
    worker.sig_status.connect(statuses.append)
    worker.sig_sources.connect(sources.append)
    worker.sig_finished.connect(finished.append)

    async def mock_execute(prompt, on_chunk, on_status, on_sources, on_tool_activity=None):
        on_status("Status: running")
        on_chunk("Result data")
        on_sources([{"url": "https://test.com", "title": "Test"}])
        return "Result data"

    with patch.object(worker.simple_service, "execute_query", side_effect=mock_execute):
        worker.start()
        worker.wait(5000)
        qapp.processEvents()

    assert chunks == ["Result data"]
    assert statuses == ["Status: running"]
    assert sources == [[{"url": "https://test.com", "title": "Test"}]]
    assert finished == ["Result data"]


def test_worker_agent_mode_execution(qapp):
    """Verify worker execution in agent mode emits thoughts and tool activities."""
    worker = AgentWorker(prompt="Agent test", mode="agent")

    thoughts = []
    tools = []
    finished = []

    worker.sig_thought.connect(thoughts.append)
    worker.sig_tool_activity.connect(lambda n, a: tools.append((n, a)))
    worker.sig_finished.connect(finished.append)

    async def mock_agent_exec(prompt, on_chunk, on_thought, on_status, on_tool_activity):
        on_thought("Reasoning step")
        on_tool_activity("calc", {"exp": "2+2"})
        on_chunk("Done")
        return "Done"

    with patch.object(worker.agent_service, "execute_query", side_effect=mock_agent_exec):
        worker.start()
        worker.wait(5000)
        qapp.processEvents()

    assert thoughts == ["Reasoning step"]
    assert tools == [("calc", {"exp": "2+2"})]
    assert finished == ["Done"]


def test_worker_cli_mode_execution(qapp):
    """Verify worker execution in cli mode calls agy_service."""
    worker = AgentWorker(prompt="CLI test", mode="cli")

    chunks = []
    finished = []
    worker.sig_chunk.connect(chunks.append)
    worker.sig_finished.connect(finished.append)

    async def mock_cli_exec(prompt, on_chunk, on_thought, on_status, on_tool_activity):
        on_chunk("AGY output")
        return "AGY output"

    with patch.object(worker.agy_service, "execute_query", side_effect=mock_cli_exec):
        worker.start()
        worker.wait(5000)
        qapp.processEvents()

    assert chunks == ["AGY output"]
    assert finished == ["AGY output"]


def test_worker_cancellation_suppresses_signals(qapp):
    """Verify cancellation suppresses chunk, status, sources, and finished signals."""
    worker = AgentWorker(prompt="Cancel test", mode="simple")

    emitted = []
    worker.sig_chunk.connect(lambda c: emitted.append(("chunk", c)))
    worker.sig_finished.connect(lambda f: emitted.append(("finished", f)))
    worker.sig_error.connect(lambda e: emitted.append(("error", e)))

    async def mock_long_exec(prompt, on_chunk, on_status, on_sources, on_tool_activity=None):
        worker.cancel()
        on_chunk("Should not emit")
        return "Should not finish"

    with patch.object(worker.simple_service, "execute_query", side_effect=mock_long_exec):
        worker.start()
        worker.wait(5000)
        qapp.processEvents()

    assert emitted == []


def test_worker_error_emission(qapp):
    """Verify uncaught exception emits user-friendly sig_error when not cancelled."""
    worker = AgentWorker(prompt="Error test", mode="simple")

    errors = []
    worker.sig_error.connect(errors.append)

    with patch.object(
        worker.simple_service,
        "execute_query",
        side_effect=RuntimeError("API_KEY_INVALID"),
    ):
        worker.start()
        worker.wait(5000)
        qapp.processEvents()

    assert len(errors) == 1
    assert "Invalid Gemini API Key" in errors[0]
