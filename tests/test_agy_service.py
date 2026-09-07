"""Unit tests for AgyCliService (Mode 3)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.ai.agy_service import AgyCliService


@pytest.fixture
def service():
    return AgyCliService()


def test_agy_service_streaming_tokens(service):
    """Verify agy stream-json output is parsed and chunks are emitted."""
    async def _run():
        lines = [
            b'{"event":"init","conversation_id":"123"}\n',
            b'{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"Hello "}}\n',
            b'{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"from AGY!"}}\n',
            b'{"event":"result","result":{"response":"Hello from AGY!"}}\n',
        ]

        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=lines + [b""])

        mock_proc = MagicMock()
        mock_proc.stdout = mock_stdout
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0

        chunks = []
        statuses = []

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.execute_query(
                prompt="Hi",
                on_chunk=chunks.append,
                on_thought=lambda _: None,
                on_status=statuses.append,
                on_tool_activity=lambda n, a: None,
            )

        assert result == "Hello from AGY!"
        assert chunks == ["Hello ", "from AGY!"]
        assert any("AGY engine initialized" in s for s in statuses)

    asyncio.run(_run())


def test_agy_service_cancellation(service):
    """Verify cancellation terminates process."""
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.pid = 99999
    service._process = mock_proc

    with patch("subprocess.run") as mock_run:
        service.cancel()
        assert service._is_cancelled is True
        mock_run.assert_called()

