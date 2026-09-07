"""AGY CLI Mode service: Executes prompts via the Antigravity CLI ('agy') engine."""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from typing import Callable, List, Optional

from ..config import config

logger = logging.getLogger(__name__)


class AgyCliService:
    """Handles Mode 3 (AGY CLI Mode): Streams responses, thoughts, and tool execution from the 'agy' CLI."""

    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._is_cancelled = False

    def cancel(self):
        """Cancels the active agy CLI subprocess."""
        self._is_cancelled = True
        if self._process and self._process.returncode is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        check=False,
                    )
                else:
                    self._process.terminate()
            except Exception as e:
                logger.debug(f"Process kill notice: {e}")

    async def execute_query(
        self,
        prompt: str,
        on_chunk: Callable[[str], None],
        on_thought: Callable[[str], None],
        on_status: Callable[[str], None],
        on_tool_activity: Callable[[str, dict], None],
    ) -> str:
        """Executes a prompt using the Antigravity CLI in stream-json mode."""
        self._is_cancelled = False
        on_status("🚀 Launching Antigravity CLI (agy)...")

        # Locate agy executable
        agy_cmd = shutil.which("agy") or "agy"

        cmd = [
            agy_cmd,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--dangerously-skip-permissions",
        ]

        if getattr(config, "cli_model", None):
            cmd.extend(["--model", config.cli_model])

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Antigravity CLI ('agy') was not found on your PATH.\n"
                "Please verify that agy is installed and available in your environment."
            )

        full_text: List[str] = []
        final_response: str = ""

        try:
            on_status("🤖 AGY Agent reasoning...")
            assert self._process.stdout is not None
            while True:
                line = await self._process.stdout.readline()
                if not line or self._is_cancelled:
                    break

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str or not line_str.startswith("{"):
                    continue

                try:
                    data = json.loads(line_str)
                except json.JSONDecodeError:
                    continue

                event = data.get("event")

                if event == "init":
                    on_status("⚙️ AGY engine initialized")

                elif event == "step_update":
                    step = data.get("step_update", {})
                    step_type = step.get("step_type")
                    text_delta = step.get("text_delta")

                    if text_delta:
                        on_chunk(text_delta)
                        full_text.append(text_delta)

                    if step_type == "tool_call":
                        tool_name = step.get("tool_name", "tool")
                        tool_args = step.get("args", {})
                        on_status(f"⚙️ AGY executing {tool_name}...")
                        on_tool_activity(tool_name, tool_args)

                    elif step_type == "thinking":
                        thought = step.get("thought", "")
                        if thought:
                            on_thought(thought)

                elif event == "result":
                    res = data.get("result", {})
                    final_response = res.get("response", "")
                    if not full_text and final_response:
                        on_chunk(final_response)
                        full_text.append(final_response)

            await self._process.wait()

        except asyncio.CancelledError:
            self.cancel()
            raise
        finally:
            self._process = None

        if self._is_cancelled:
            return ""

        return "".join(full_text) if full_text else final_response
