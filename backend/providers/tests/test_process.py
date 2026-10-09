import os
import sys
import time

import pytest

from backend.providers.errors import ProviderError
from backend.providers.process import run_bounded


def test_runner_uses_argv_and_supplied_environment_only(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    result = run_bounded(
        [sys.executable, "-c", "import os; print('OPENAI_API_KEY' in os.environ)"],
        cwd=tmp_path,
        env={"PATH": os.defpath},
        timeout=5,
    )
    assert result.returncode == 0 and result.stdout == b"False\n"


def test_timeout_terminates_process(tmp_path):
    start = time.monotonic()
    with pytest.raises(ProviderError, match="timeout"):
        run_bounded(
            [sys.executable, "-c", "import time; time.sleep(20)"],
            cwd=tmp_path,
            env={"PATH": os.defpath},
            timeout=0.1,
        )
    assert time.monotonic() - start < 3


def test_output_limit(tmp_path):
    with pytest.raises(ProviderError, match="output_too_large"):
        run_bounded(
            [sys.executable, "-c", "print('x' * 4000001)"],
            cwd=tmp_path,
            env={"PATH": os.defpath},
            timeout=5,
        )
