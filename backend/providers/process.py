"""Bounded local scanner process runner, with no shell or inherited secrets."""

import os
import signal
import subprocess
import tempfile
import time

from backend.providers.errors import ProviderError

MAX_OUTPUT = 4_000_000


def run_bounded(argv: list[str], *, cwd, env, timeout: float) -> subprocess.CompletedProcess:
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise ProviderError("semgrep", "timeout")
                if (
                    os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size
                    > MAX_OUTPUT
                ):
                    raise ProviderError("semgrep", "output_too_large")
                time.sleep(0.02)
            if os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > MAX_OUTPUT:
                raise ProviderError("semgrep", "output_too_large")
            stdout.seek(0)
            stderr.seek(0)
            return subprocess.CompletedProcess(
                argv, process.returncode, stdout.read(), stderr.read()
            )
        finally:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            if process.poll() is None:
                process.wait()
