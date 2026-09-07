"""Lifecycle hooks for the Google Antigravity Agent to communicate with the UI."""
import copy
import logging
from typing import Callable, Optional
from google.antigravity import types
from google.antigravity.hooks import hooks

logger = logging.getLogger(__name__)


class AgentUIHookBridge:
    """Bridges Google Antigravity SDK hooks with UI callback signals."""

    def __init__(self):
        self.on_tool_start_callback: Optional[Callable[[str, dict], None]] = None
        self.on_tool_end_callback: Optional[Callable[[str, str], None]] = None
        self.on_tool_error_callback: Optional[Callable[[str, str], None]] = None
        self.is_cancelled_predicate: Optional[Callable[[], bool]] = None

    def set_callbacks(
        self,
        on_tool_start: Optional[Callable[[str, dict], None]] = None,
        on_tool_end: Optional[Callable[[str, str], None]] = None,
        on_tool_error: Optional[Callable[[str, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ):
        self.on_tool_start_callback = on_tool_start
        self.on_tool_end_callback = on_tool_end
        self.on_tool_error_callback = on_tool_error
        self.is_cancelled_predicate = is_cancelled

    def clear(self):
        """Clears callbacks to prevent memory leaks and cross-thread clobbering."""
        self.on_tool_start_callback = None
        self.on_tool_end_callback = None
        self.on_tool_error_callback = None
        self.is_cancelled_predicate = None


# Global bridge instance
hook_bridge = AgentUIHookBridge()


@hooks.pre_tool_call_decide
async def ui_pre_tool_call(data: types.ToolCall) -> types.HookResult:
    """Intercepts tool calls before execution to update UI or abort if cancelled."""
    if hook_bridge.is_cancelled_predicate and hook_bridge.is_cancelled_predicate():
        logger.info("Tool call cancelled by user.")
        return types.HookResult(allow=False)

    tool_name = getattr(data, "name", str(data))
    raw_args = getattr(data, "args", {}) or {}
    safe_args = copy.deepcopy(raw_args) if isinstance(raw_args, dict) else {}

    if hook_bridge.on_tool_start_callback:
        try:
            hook_bridge.on_tool_start_callback(tool_name, safe_args)
        except Exception as exc:
            logger.debug(f"Pre-tool callback error: {exc}")

    return types.HookResult(allow=True)


@hooks.post_tool_call
async def ui_post_tool_call(data):
    """Notifies UI that tool execution has finished."""
    tool_name = getattr(data, "name", "tool")
    result_str = str(getattr(data, "result", ""))

    if hook_bridge.on_tool_end_callback:
        try:
            hook_bridge.on_tool_end_callback(tool_name, result_str)
        except Exception as exc:
            logger.debug(f"Post-tool callback error: {exc}")


@hooks.on_tool_error
async def ui_on_tool_error(exc: Exception):
    """Notifies UI when a tool call encounters an error."""
    error_msg = str(exc)
    if hook_bridge.on_tool_error_callback:
        try:
            hook_bridge.on_tool_error_callback("error", error_msg)
        except Exception as err:
            logger.debug(f"On-tool-error callback error: {err}")
    return None
