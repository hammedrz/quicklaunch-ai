"""Simple Mode AI service: Fast streaming with Google Search grounding & Sandboxed Python Code Execution."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, List, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

from ..config import config
from .tools import (
    calculate,
    execute_python_code,
    get_clipboard,
    get_system_info,
    launch_app_or_url,
    set_clipboard,
)


class SimpleAIService:
    """Handles Mode 1 (Simple Mode): Fast streaming, Google Search grounding, sandboxed code & system tools."""

    def __init__(self):
        self._client: Optional[genai.Client] = None
        self._is_cancelled: bool = False
        self._tools_map = {
            "execute_python_code": execute_python_code,
            "calculate": calculate,
            "get_system_info": get_system_info,
            "get_clipboard": get_clipboard,
            "set_clipboard": set_clipboard,
            "launch_app_or_url": launch_app_or_url,
        }

    def cancel(self):
        """Sets internal cancellation flag to break stream iteration."""
        self._is_cancelled = True

    def _get_client(self) -> genai.Client:
        key = config.gemini_api_key or ""
        if not key:
            raise ValueError(
                "Gemini API key is not configured.\n"
                "Please set GEMINI_API_KEY in your .env file or Windows environment variables."
            )
        if self._client is None:
            self._client = genai.Client(api_key=key)
        return self._client

    async def execute_query(
        self,
        prompt: str,
        on_chunk: Callable[[str], None],
        on_status: Callable[[str], None],
        on_sources: Callable[[List[Dict[str, str]]], None],
        on_tool_activity: Optional[Callable[[str, dict], None]] = None,
    ) -> str:
        """Executes a simple mode prompt using native asynchronous streaming and AFC."""
        self._is_cancelled = False
        client = self._get_client()
        on_status("⚡ Processing with Gemini...")

        # Build tools list
        tools: list = []
        if config.search_enabled:
            tools.append({"google_search": {}})

        tools.extend([
            execute_python_code,
            calculate,
            get_system_info,
            get_clipboard,
            set_clipboard,
            launch_app_or_url,
        ])

        system_instruction = (
            "You are QuickLaunch AI, a fast and helpful desktop assistant on Windows. "
            "You provide clear, concise, well-structured answers using clean Markdown. "
            "Use the search tool for up-to-date web information when needed. "
            "Use execute_python_code to run calculations, simulate logic, or test Python code in a safe sandbox. "
            "Use system tools when the user asks about their PC, clipboard, or launching applications. "
            "Always be succinct and prioritize direct, actionable answers."
        )

        has_search = any(isinstance(t, dict) and "google_search" in t for t in tools)

        generate_config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_instruction,
            temperature=0.7,
        )

        try:
            chat = client.aio.chats.create(
                model=config.simple_model,
                config=generate_config,
            )
            response_stream = await chat.send_message_stream(prompt)
            return await self._stream_response(
                response_stream=response_stream,
                on_chunk=on_chunk,
                on_status=on_status,
                on_sources=on_sources,
                on_tool_activity=on_tool_activity,
            )
        except Exception as exc:
            msg = str(exc)
            # If Google Search Grounding quota was exceeded, gracefully retry with standard tools
            if has_search and ("429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()):
                logger.warning(
                    "Google Search grounding quota exceeded on API key. Falling back to direct Gemini generation without web search."
                )
                on_status("⚠️ Web Search quota reached; generating answer directly...")
                func_tools = [t for t in tools if not (isinstance(t, dict) and "google_search" in t)]
                fallback_config = types.GenerateContentConfig(
                    tools=func_tools,
                    system_instruction=system_instruction,
                    temperature=0.7,
                )
                chat = client.aio.chats.create(
                    model=config.simple_model,
                    config=fallback_config,
                )
                response_stream = await chat.send_message_stream(prompt)
                return await self._stream_response(
                    response_stream=response_stream,
                    on_chunk=on_chunk,
                    on_status=on_status,
                    on_sources=on_sources,
                    on_tool_activity=on_tool_activity,
                )
            raise

    async def _stream_response(
        self,
        response_stream,
        on_chunk: Callable[[str], None],
        on_status: Callable[[str], None],
        on_sources: Callable[[List[Dict[str, str]]], None],
        on_tool_activity: Optional[Callable[[str, dict], None]],
    ) -> str:
        """Parses an async response stream, emitting text chunks, grounding citations, and tool signals."""
        full_text: List[str] = []
        collected_sources: List[Dict[str, str]] = []
        seen_urls = set()
        last_chunk = None

        async for chunk in response_stream:
            last_chunk = chunk
            if self._is_cancelled:
                break

            # 1. Detect function calls during AFC execution to update UI status
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        func_name = getattr(fc, "name", "tool")
                        func_args = getattr(fc, "args", {}) or {}
                        on_status(f"⚙️ Running tool: {func_name}...")
                        if on_tool_activity:
                            on_tool_activity(func_name, func_args)

            # 2. Extract text tokens
            if chunk.text:
                on_chunk(chunk.text)
                full_text.append(chunk.text)

            # 3. Extract grounding metadata (Google Search citations)
            if chunk.candidates:
                candidate = chunk.candidates[0]
                grounding = getattr(candidate, "grounding_metadata", None)
                if grounding:
                    queries = getattr(grounding, "web_search_queries", None)
                    if queries:
                        query_str = ", ".join(queries)
                        on_status(f"🌐 Searched Google: {query_str}")

                    chunks = getattr(grounding, "grounding_chunks", None)
                    if chunks:
                        new_sources_found = False
                        for c in chunks:
                            web = getattr(c, "web", None)
                            if web:
                                uri = getattr(web, "uri", "")
                                title = getattr(web, "title", "") or uri
                                if uri and uri not in seen_urls:
                                    seen_urls.add(uri)
                                    collected_sources.append({"title": title, "url": uri})
                                    new_sources_found = True
                        if new_sources_found:
                            on_sources(list(collected_sources))

        # Check for safety filter withholding
        if not full_text and not self._is_cancelled and last_chunk:
            if last_chunk.candidates and last_chunk.candidates[0].finish_reason:
                reason = str(last_chunk.candidates[0].finish_reason)
                if "SAFETY" in reason:
                    warning = "⚠️ Response was withheld due to safety policy filters."
                    on_chunk(warning)
                    full_text.append(warning)

        return "".join(full_text)
