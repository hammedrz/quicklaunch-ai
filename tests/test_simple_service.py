"""Unit tests for SimpleAIService (Mode 1)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.ai.simple_service import SimpleAIService
from src.config import config


@pytest.fixture
def service():
    return SimpleAIService()


def test_simple_service_missing_api_key(service):
    """Verify ValueError is raised if API key is not configured."""
    async def _run():
        with patch.object(config, "gemini_api_key", ""):
            service._client = None
            with pytest.raises(ValueError, match="Gemini API key is not configured"):
                await service.execute_query(
                    prompt="test",
                    on_chunk=lambda c: None,
                    on_status=lambda s: None,
                    on_sources=lambda src: None,
                )
    asyncio.run(_run())


def test_simple_service_streaming_and_grounding(service):
    """Verify streaming tokens and Google Search grounding citations are parsed and emitted."""
    async def _run():
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Hello "
        mock_chunk1.candidates = []

        mock_web1 = MagicMock()
        mock_web1.uri = "https://example.com/ai"
        mock_web1.title = "Example AI"

        mock_grounding_chunk = MagicMock()
        mock_grounding_chunk.web = mock_web1

        mock_metadata = MagicMock()
        mock_metadata.web_search_queries = ["latest AI news"]
        mock_metadata.grounding_chunks = [mock_grounding_chunk]

        mock_candidate = MagicMock()
        mock_candidate.grounding_metadata = mock_metadata
        mock_candidate.content = None
        mock_candidate.finish_reason = None

        mock_chunk2 = MagicMock()
        mock_chunk2.text = "world!"
        mock_chunk2.candidates = [mock_candidate]

        async def mock_stream_gen():
            yield mock_chunk1
            yield mock_chunk2

        mock_chat = MagicMock()
        mock_chat.send_message_stream = AsyncMock(return_value=mock_stream_gen())

        mock_client = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        received_chunks = []
        received_statuses = []
        received_sources = []

        service._client = mock_client
        with patch.object(config, "gemini_api_key", "test-key-456"):
            result = await service.execute_query(
                prompt="What is new in AI?",
                on_chunk=received_chunks.append,
                on_status=received_statuses.append,
                on_sources=received_sources.extend,
            )

        assert result == "Hello world!"
        assert received_chunks == ["Hello ", "world!"]
        assert any("Searched Google: latest AI news" in s for s in received_statuses)
        assert len(received_sources) == 1
        assert received_sources[0] == {"title": "Example AI", "url": "https://example.com/ai"}

    asyncio.run(_run())
