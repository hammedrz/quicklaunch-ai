"""Edge case and security robustness tests for QuickLaunch AI."""
import json
import pytest

from src.ai.tools.system_tools import calculate
from src.ai.sandbox import SandboxedPythonRunner
from src.state_manager import StateManager
from src.config import _validate_mode, _validate_timeout, _validate_hotkey


def test_calculator_security_and_edge_cases():
    """Verify AST calculator safely handles malformed, exploit, and overflow inputs."""
    # Division by zero
    res = calculate("10 / 0")
    assert "Error" in res and "zero" in res.lower()

    # Modulo by zero
    res = calculate("10 % 0")
    assert "Error" in res and "zero" in res.lower()

    # Security exploit attempt: __class__ attribute access
    res = calculate("().__class__.__base__")
    assert "Error" in res or "Security error" in res

    # Security exploit attempt: builtins access
    res = calculate("__import__('os').system('calc')")
    assert "Error" in res

    # Disallowed function calls
    res = calculate("eval('2+2')")
    assert "Error" in res

    # Huge power exponent DoS prevention (> 10,000)
    res = calculate("2 ** 99999999")
    assert "Error" in res and "Exponent too large" in res

    # Valid complex math
    res = calculate("sqrt(144) + sin(0) + log10(100)")
    assert float(res) == pytest.approx(14.0)


def test_sandbox_huge_stdout_truncation():
    """Verify runaway output is cleanly truncated without memory exhaustion."""
    runner = SandboxedPythonRunner(timeout_seconds=5, max_output_chars=500)
    # Output 2,000 characters
    code = "print('A' * 2000)"
    result = runner.execute(code)

    assert result.exit_code == 0
    assert len(result.stdout) <= 600  # 500 + truncation warning message
    assert "truncated" in result.stdout


def test_sandbox_syntax_error():
    """Verify Python syntax errors are captured cleanly in result.stderr."""
    runner = SandboxedPythonRunner(timeout_seconds=5)
    result = runner.execute("def incomplete_func(")
    assert result.exit_code != 0
    assert "SyntaxError" in result.stderr


def test_state_manager_corrupted_json_recovery(tmp_path):
    """Verify StateManager recovers gracefully from a corrupted history.json file."""
    history_file = tmp_path / "history.json"
    history_file.write_text("{corrupted json invalid syntax", encoding="utf-8")

    mgr = StateManager()
    mgr.history_file = history_file
    assert mgr.load_history() == []

    # Can write new history cleanly
    updated = mgr.add_history("valid query")
    assert updated == ["valid query"]
    assert mgr.load_history() == ["valid query"]


def test_config_mode_validation():
    """Verify invalid mode values are validated and fallback to simple."""
    assert _validate_mode("ultra_super_mode") == "simple"
    assert _validate_mode("cli") == "cli"
    assert _validate_mode("agent") == "agent"
    assert _validate_mode("simple") == "simple"


def test_config_timeout_bounds():
    """Verify timeout validation enforces min/max bounds."""
    # Out of bounds (< 0.5) falls back to default 5.0
    assert _validate_timeout("0.1", default=5.0) == 5.0
    # Out of bounds (> 300) falls back to default 5.0
    assert _validate_timeout("999.0", default=5.0) == 5.0
    # Valid timeout
    assert _validate_timeout("15.5", default=5.0) == 15.5
    # Invalid string falls back to default
    assert _validate_timeout("not-a-number", default=5.0) == 5.0


def test_config_hotkey_validation():
    """Verify hotkey validation ensures modifier and key."""
    assert _validate_hotkey("ctrl+space") == "ctrl+space"
    assert _validate_hotkey("alt+space") == "alt+space"
    assert _validate_hotkey("invalid", default="ctrl+space") == "ctrl+space"
