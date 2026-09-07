"""Code execution tool using SandboxedPythonRunner."""
from ..sandbox import SandboxedPythonRunner
from ...config import config


def execute_python_code(code: str) -> str:
    """Executes a snippet of Python code in an isolated subprocess sandbox.
    
    Use this tool when you need to calculate complex math, process data,
    verify algorithmic logic, test code behavior, or generate program outputs.

    Args:
        code: Valid Python code string to execute. Any outputs must be printed using print().

    Returns:
        The execution output (stdout/stderr), execution duration, and exit code.
    """
    timeout = getattr(config, "sandbox_timeout_seconds", 5.0)
    runner = SandboxedPythonRunner(timeout_seconds=timeout)
    result = runner.execute(code)
    
    if result.timed_out:
        return f"[Timeout Error]: {result.error} (duration: {result.duration_ms}ms)"
    
    if result.error:
        return f"[Execution Error]: {result.error}"

    output = []
    if result.stdout:
        output.append(f"Standard Output:\n{result.stdout}")
    if result.stderr:
        output.append(f"Standard Error:\n{result.stderr}")
    if not output:
        output.append("(No output produced. Remember to use print() to view results)")
    
    output.append(f"\n[Exit code: {result.exit_code}, Elapsed: {result.duration_ms}ms]")
    return "\n".join(output)
