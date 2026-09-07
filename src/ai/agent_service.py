"""Agent Mode AI service: Autonomous Google Antigravity Agent with thought streaming, hooks, and full tools."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Callable, Dict, List, Optional

from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig, types
from google.antigravity.policy import allow_all

from ..config import config
from .hooks import hook_bridge, ui_on_tool_error, ui_post_tool_call, ui_pre_tool_call
from .tools import (
    calculate,
    execute_python_code,
    get_clipboard,
    get_system_info,
    launch_app_or_url,
    set_clipboard,
)

logger = logging.getLogger(__name__)


class AntigravityAgentService:
    """Handles Mode 2 (Full Antigravity Agent Mode): Autonomous agent, reasoning stream, hooks, and deep tools."""

    def __init__(self):
        self._agent: Optional[Agent] = None
        self._current_response: Optional[types.ChatResponse] = None
        self._is_cancelled: bool = False

    def cancel(self):
        """Cancels active backend agent inference."""
        self._is_cancelled = True
        if self._current_response is not None:
            try:
                asyncio.create_task(self._current_response.cancel())
            except Exception as e:
                logger.debug(f"Antigravity cancellation notice: {e}")

    def _ensure_api_key(self):
        key = config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "Gemini API key is not configured.\n"
                "Please set GEMINI_API_KEY in your .env file or Windows environment variables."
            )
        os.environ["GEMINI_API_KEY"] = key

    async def execute_query(
        self,
        prompt: str,
        on_chunk: Callable[[str], None],
        on_thought: Callable[[str], None],
        on_status: Callable[[str], None],
        on_tool_activity: Callable[[str, dict], None],
    ) -> str:
        """Executes an autonomous agent query with real-time interleaved reasoning, tools, and token streaming."""
        self._ensure_api_key()
        self._is_cancelled = False
        on_status("🤖 Antigravity Agent initializing...")

        # Setup hook bridge callbacks to update UI
        def handle_tool_start(name: str, args: dict):
            if self._is_cancelled:
                return
            status_desc = f"⚙️ Agent running {name}..."
            if name == "search_web" or "search" in name.lower():
                query = args.get("query", "")
                status_desc = f"🌐 Searching web: {query}" if query else "🌐 Searching web..."
            elif name == "execute_python_code":
                status_desc = "🐍 Executing sandboxed Python code..."
            elif name == "read_url_content":
                status_desc = f"📄 Reading URL: {args.get('Url', '')}"
            on_status(status_desc)
            on_tool_activity(name, args)

        def handle_tool_end(name: str, result: str):
            if not self._is_cancelled:
                on_status(f"✓ Tool '{name}' completed")

        def handle_tool_error(name: str, err: str):
            if not self._is_cancelled:
                on_status(f"⚠️ Tool error in '{name}': {err}")

        hook_bridge.set_callbacks(
            on_tool_start=handle_tool_start,
            on_tool_end=handle_tool_end,
            on_tool_error=handle_tool_error,
            is_cancelled=lambda: self._is_cancelled,
        )

        # Configure built-in capabilities
        enabled_tools = [
            types.BuiltinTools.SEARCH_WEB,
            types.BuiltinTools.READ_URL_CONTENT,
            types.BuiltinTools.VIEW_FILE,
        ]

        agent_config = LocalAgentConfig(
            model=config.agent_model,
            policies=[allow_all()],
            capabilities=CapabilitiesConfig(enabled_tools=enabled_tools),
            tools=[
                execute_python_code,
                calculate,
                get_system_info,
                get_clipboard,
                set_clipboard,
                launch_app_or_url,
            ],
            hooks=[
                ui_pre_tool_call,
                ui_post_tool_call,
                ui_on_tool_error,
            ],
            system_instructions=(
                "You are an expert autonomous AI desktop assistant for Windows, powered by the Google Antigravity SDK. "
                "You have full agency to reason, search the web, execute sandboxed Python code, inspect system status, "
                "and read URLs to answer the user's queries thoroughly. "
                "Provide thoughtful, well-reasoned answers formatted in clean Markdown."
            ),
        )

        full_text: List[str] = []

        try:
            async with Agent(agent_config) as agent:
                self._agent = agent
                on_status("🧠 Agent reasoning...")
                response = await agent.chat(prompt)
                self._current_response = response

                # Stream thoughts if available
                if hasattr(response, "thoughts"):
                    try:
                        async for thought in response.thoughts:
                            if self._is_cancelled:
                                break
                            if thought:
                                on_thought(str(thought))
                    except Exception:
                        pass

                on_status("✍️ Synthesizing response...")

                # Stream tokens
                async for token in response:
                    if self._is_cancelled:
                        await response.cancel()
                        break
                    if token:
                        on_chunk(str(token))
                        full_text.append(str(token))

        except types.AntigravityCancelledError:
            logger.info("Antigravity turn cancelled.")
        finally:
            self._current_response = None
            self._agent = None
            hook_bridge.clear()

        return "".join(full_text)

    def reset_session(self):
        """Resets the agent session context."""
        self.cancel()
        self._agent = None
        self._current_response = None
