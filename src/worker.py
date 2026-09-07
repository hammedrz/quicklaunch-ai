"""Background QThread worker executing async AI services without blocking Qt GUI."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from .ai.agent_service import AntigravityAgentService
from .ai.agy_service import AgyCliService
from .ai.simple_service import SimpleAIService

logger = logging.getLogger(__name__)


class AgentWorker(QThread):
    """Worker thread running Python asyncio loop for AI operations across all 3 modes."""

    sig_status = Signal(str)
    sig_thought = Signal(str)
    sig_chunk = Signal(str)
    sig_sources = Signal(list)
    sig_tool_activity = Signal(str, dict)
    sig_finished = Signal(str)
    sig_error = Signal(str)

    def __init__(self, prompt: str, mode: str = "simple", parent: Optional[QObject] = None):
        super().__init__(parent)
        self.prompt = prompt
        self.mode = mode
        self.simple_service = SimpleAIService()
        self.agent_service = AntigravityAgentService()
        self.agy_service = AgyCliService()
        self._is_cancelled = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Task] = None

    def cancel(self):
        """Thread-safe cancellation of the active worker and underlying AI execution."""
        self._is_cancelled = True

        if self.mode == "agent":
            self.agent_service.cancel()
        elif self.mode == "cli":
            self.agy_service.cancel()
        else:
            self.simple_service.cancel()

        if self._loop and self._loop.is_running() and self._task and not self._task.done():
            self._loop.call_soon_threadsafe(self._task.cancel)

    def run(self):
        """Runs the asyncio task inside this worker thread with graceful teardown."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        try:
            self._task = loop.create_task(self._execute())
            loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            logger.info("AgentWorker asyncio task cancelled.")
        except Exception as exc:
            if not self._is_cancelled:
                msg = str(exc)
                if any(err in msg for err in ("429", "RESOURCE_EXHAUSTED", "API_KEY_INVALID", "400", "404", "Timeout")):
                    logger.warning(f"Worker API error: {exc}")
                else:
                    logger.exception("Unhandled error in AgentWorker execution")
                self.sig_error.emit(self._format_user_friendly_error(exc))
        finally:
            self._cleanup_loop(loop)
            asyncio.set_event_loop(None)
            self._loop = None
            self._task = None

    def _cleanup_loop(self, loop: asyncio.AbstractEventLoop):
        """Cancels remaining tasks and gracefully shuts down the loop."""
        try:
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            loop.run_until_complete(loop.shutdown_asyncgens())
            if hasattr(loop, "shutdown_default_executor"):
                loop.run_until_complete(loop.shutdown_default_executor())
        except Exception as exc:
            logger.debug(f"Loop cleanup notice: {exc}")
        finally:
            loop.close()

    async def _execute(self):
        if self._is_cancelled:
            return

        def on_chunk(chunk: str):
            if not self._is_cancelled and chunk:
                self.sig_chunk.emit(chunk)

        def on_thought(thought: str):
            if not self._is_cancelled and thought:
                self.sig_thought.emit(thought)

        def on_status(status: str):
            if not self._is_cancelled and status:
                self.sig_status.emit(status)

        def on_sources(sources: List[Dict[str, str]]):
            if not self._is_cancelled and sources:
                self.sig_sources.emit(sources)

        def on_tool(name: str, args: dict):
            if not self._is_cancelled:
                self.sig_tool_activity.emit(name, args)

        result = ""
        if self.mode == "agent":
            result = await self.agent_service.execute_query(
                prompt=self.prompt,
                on_chunk=on_chunk,
                on_thought=on_thought,
                on_status=on_status,
                on_tool_activity=on_tool,
            )
        elif self.mode == "cli":
            result = await self.agy_service.execute_query(
                prompt=self.prompt,
                on_chunk=on_chunk,
                on_thought=on_thought,
                on_status=on_status,
                on_tool_activity=on_tool,
            )
        else:
            result = await self.simple_service.execute_query(
                prompt=self.prompt,
                on_chunk=on_chunk,
                on_status=on_status,
                on_sources=on_sources,
                on_tool_activity=on_tool,
            )

        if not self._is_cancelled:
            self.sig_finished.emit(result)

    @staticmethod
    def _format_user_friendly_error(exc: Exception) -> str:
        msg = str(exc)
        if "API_KEY_INVALID" in msg or ("400" in msg and "API key" in msg):
            return "Invalid Gemini API Key. Please check your key in settings or the .env file."
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            return (
                "Gemini API rate limit or quota exceeded.\n\n"
                "• Your Google Gemini API quota has been reached.\n"
                "• **Workaround**: Press **Tab** to switch to **🚀 AGY CLI Mode** which uses the Antigravity engine directly."
            )
        if "404" in msg and "models/" in msg:
            return f"Requested model was not found or is unavailable: {msg}"
        if "Timeout" in msg or "timed out" in msg.lower():
            return "Request timed out. Please verify your network connection and try again."
        return msg
