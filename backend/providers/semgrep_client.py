"""PLANNED real Semgrep CLI adapter; Guardian access is not runtime scanning."""

from pathlib import Path
from typing import Protocol

from backend.providers.contracts import ScanResult


class SemgrepScanner(Protocol):
    def scan_repository(self, workspace: Path) -> ScanResult: ...
