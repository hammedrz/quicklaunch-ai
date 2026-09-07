"""Unit tests for AntigravityAgentService (Mode 2)."""
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.ai.agent_service import AntigravityAgentService
from src.ai.hooks import hook_bridge
from src.config import config


@pytest.fixture
def service():
    return AntigravityAgentService()


import asyncio


def test_agent_service_missing_api_key(service):
    """Verify ValueError when API key is missing from config and environment."""
    async def _run():
        with patch.object(config, "gemini_api_key", ""), \
             patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
            with pytest.raises(ValueError, match="Gemini API key is not configured"):
                await service.execute_query(
                    prompt="test",
                    on_chunk=lambda c: None,
                    on_thought=lambda t: None,
                    on_status=lambda s: None,
                    on_tool_activity=lambda n, a: None,
                )
    asyncio.run(_run())


def test_agent_service_execution_flow(service):
    """Verify Agent context manager, thought streaming, and token streaming."""
    async def _run():
        async def mock_thoughts():
            yield "Thinking step 1: analyze input\n"
            yield "Thinking step 2: choose tool\n"

        async def mock_tokens():
            yield "Autonomous "
            yield "response."

        mock_response = MagicMock()
        mock_response.thoughts = mock_thoughts()
        mock_response.__aiter__ = lambda self: mock_tokens()

        mock_agent_instance = MagicMock()
        mock_agent_instance.chat = AsyncMock(return_value=mock_response)

        mock_agent_ctx = MagicMock()
        mock_agent_ctx.__aenter__ = AsyncMock(return_value=mock_agent_instance)
        mock_agent_ctx.__aexit__ = AsyncMock(return_value=None)

        received_chunks = []
        received_thoughts = []
        received_statuses = []
        received_tools = []

        with patch.object(config, "gemini_api_key", "test-agent-key"), \
             patch("src.ai.agent_service.Agent", return_value=mock_agent_ctx):
            
            result = await service.execute_query(
                prompt="Perform deep task",
                on_chunk=received_chunks.append,
                on_thought=received_thoughts.append,
                on_status=received_statuses.append,
                on_tool_activity=lambda n, a: received_tools.append((n, a)),
            )

        assert result == "Autonomous response."
        assert received_chunks == ["Autonomous ", "response."]
        assert len(received_thoughts) == 2
        assert "Thinking step 1" in received_thoughts[0]
        assert any("Agent reasoning..." in s for s in received_statuses)
        assert any("Synthesizing response..." in s for s in received_statuses)

    asyncio.run(_run())

