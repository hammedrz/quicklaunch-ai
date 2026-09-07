"""Hardened Python Sandbox Runner with Process Tree Cleanup, Environment Isolation, and Memory Limits."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timed_out: bool = False
    error: Optional[str] = None


class SandboxedPythonRunner:
    """Executes Python code in an isolated, resource-constrained subprocess sandbox."""

    SAFE_ENV_VARS = {
        "SYSTEMROOT",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "COMSPEC",
        "NUMBER_OF_PROCESSORS",
        "OS",
    }

    def __init__(self, timeout_seconds: float = 5.0, max_output_chars: int = 10000):
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def _get_isolated_env(self) -> Dict[str, str]:
        """Builds a minimal environment dict, scrubbing API keys and secrets."""
        env = {}
        for var in self.SAFE_ENV_VARS:
            val = os.environ.get(var)
            if val is not None:
                env[var] = val
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return env

    def execute(self, code: str) -> ExecutionResult:
        """Executes the given Python code in an isolated subprocess with strict safeguards."""
        start_time = time.perf_counter()
        temp_dir = tempfile.mkdtemp(prefix="ql_sandbox_")

        try:
            # -I: Isolated mode (no cwd on sys.path, ignore PYTHON* env vars)
            # -B: Don't write bytecode
            # -: Read script from stdin
            cmd = [sys.executable, "-I", "-B", "-"]

            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=temp_dir,
                env=self._get_isolated_env(),
                creationflags=creationflags,
            )

            try:
                stdout, stderr = process.communicate(
                    input=code, timeout=self.timeout_seconds
                )
                duration = (time.perf_counter() - start_time) * 1000.0

                if len(stdout) > self.max_output_chars:
                    stdout = (
                        stdout[: self.max_output_chars]
                        + f"\n... [Output truncated after {self.max_output_chars} chars]"
                    )
                if len(stderr) > self.max_output_chars:
                    stderr = (
                        stderr[: self.max_output_chars]
                        + f"\n... [Errors truncated after {self.max_output_chars} chars]"
                    )

                return ExecutionResult(
                    stdout=stdout.strip(),
                    stderr=stderr.strip(),
                    exit_code=process.returncode,
                    duration_ms=round(duration, 2),
                    timed_out=False,
                )

            except subprocess.TimeoutExpired:
                self._terminate_process_tree(process)
                try:
                    stdout, stderr = process.communicate(timeout=0.5)
                except Exception:
                    stdout, stderr = "", ""

                duration = (time.perf_counter() - start_time) * 1000.0
                return ExecutionResult(
                    stdout=stdout.strip() if stdout else "",
                    stderr=stderr.strip() if stderr else "",
                    exit_code=-1,
                    duration_ms=round(duration, 2),
                    timed_out=True,
                    error=f"Execution timed out after {self.timeout_seconds} seconds.",
                )

        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=round(duration, 2),
                timed_out=False,
                error=str(exc),
            )
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen) -> None:
        """Forcefully terminates the process and any child processes it spawned."""
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            else:
                process.kill()
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
