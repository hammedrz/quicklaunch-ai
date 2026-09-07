"""Tests for sandboxed Python code execution."""
import pytest
from src.ai.sandbox import SandboxedPythonRunner


@pytest.fixture
def runner():
    return SandboxedPythonRunner(timeout_seconds=3.0)


def test_simple_print(runner):
    result = runner.execute("print('hello world')")
    assert result.stdout == "hello world"
    assert result.exit_code == 0
    assert not result.timed_out


def test_math_calculation(runner):
    result = runner.execute("print(2 ** 10)")
    assert result.stdout == "1024"
    assert result.exit_code == 0


def test_multiline_code(runner):
    code = """
total = 0
for i in range(5):
    total += i
print(total)
"""
    result = runner.execute(code)
    assert result.stdout == "10"
    assert result.exit_code == 0


def test_syntax_error(runner):
    result = runner.execute("def foo(")
    assert result.exit_code != 0
    assert result.stderr  # Should contain error message


def test_runtime_error(runner):
    result = runner.execute("print(1/0)")
    assert result.exit_code != 0
    assert "ZeroDivisionError" in result.stderr


def test_timeout():
    fast_runner = SandboxedPythonRunner(timeout_seconds=1.0)
    result = fast_runner.execute("import time; time.sleep(10)")
    assert result.timed_out is True
    assert result.error is not None
    assert "timed out" in result.error.lower()


def test_no_output(runner):
    result = runner.execute("x = 42")
    assert result.stdout == ""
    assert result.exit_code == 0


def test_stderr_capture(runner):
    result = runner.execute("import sys; print('err', file=sys.stderr)")
    assert "err" in result.stderr


def test_duration_tracked(runner):
    result = runner.execute("print('fast')")
    assert result.duration_ms > 0
