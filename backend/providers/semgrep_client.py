"""Actual local Semgrep CE scans. Static findings never establish a verdict."""

import hashlib
import math
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path

from backend.api.schemas import Finding
from backend.providers.contracts import ScanResult
from backend.providers.errors import ProviderError
from backend.providers.http import decode_json
from backend.providers.process import run_bounded

BUNDLED_RULES = Path(__file__).parent / "rules" / "python-security.yml"


@dataclass(frozen=True)
class ScanFinding:
    finding_id: str
    rule_id: str
    path: str
    line: int
    end_line: int


@dataclass(frozen=True)
class ScanReport:
    result: ScanResult
    locations: tuple[ScanFinding, ...] = ()
    diagnostics: tuple[str, ...] = ()
    scanned_paths: tuple[str, ...] = ()
    skipped_paths: tuple[str, ...] = ()
    exit_code: int | None = None
    rulesets: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ("Static rule matches only; absence is not a security verdict.",)


def _no_symlink(path: Path) -> bool:
    return not any(p.is_symlink() for p in (path, *path.parents))


class SemgrepScanner:
    def __init__(
        self,
        *,
        approved_roots: Collection[Path],
        rules: Collection[Path] | None = None,
        executable: str = "semgrep",
        timeout: float = 30,
        source_suffixes: Collection[str] = (".py",),
        runner: Callable = run_bounded,
    ):
        if not approved_roots:
            raise ValueError("Explicit approved source roots required")
        roots = [Path(p).absolute() for p in approved_roots]
        if any(not p.is_dir() or not _no_symlink(p) for p in roots):
            raise ValueError("Approved roots must be real directories without symlinks")
        if not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("timeout must be in (0, 60]")
        if not source_suffixes or any(
            not re.fullmatch(r"\.[A-Za-z0-9]+", suffix) for suffix in source_suffixes
        ):
            raise ValueError("Explicit source language suffixes required")
        self.source_suffixes = frozenset(source_suffixes)
        self.approved_roots = tuple(p.resolve() for p in roots)
        self.rules = tuple(
            Path(p).absolute() for p in (rules if rules is not None else [BUNDLED_RULES])
        )
        if not self.rules or any(not p.is_file() or not _no_symlink(p) for p in self.rules):
            raise ValueError("Pinned local rule files required")
        self._rules_content = tuple(p.read_bytes() for p in self.rules)
        if sum(len(data) for data in self._rules_content) > 1_000_000:
            raise ValueError("Ruleset too large")
        # Ordered content hashes identify exact rule bytes independent of temporary paths.
        self.ruleset_hash = hashlib.sha256(
            b"".join(hashlib.sha256(data).digest() for data in self._rules_content)
        ).hexdigest()
        self.executable = shutil.which(executable) or executable
        self.timeout = timeout
        self.runner = runner

    def scan_repository(self, workspace: Path) -> ScanResult:
        return self.scan_with_details(workspace).result

    def scan_with_details(self, workspace: Path) -> ScanReport:
        workspace = Path(workspace).absolute()
        if (
            not workspace.is_dir()
            or not _no_symlink(workspace)
            or not any(workspace.resolve().is_relative_to(root) for root in self.approved_roots)
        ):
            raise ProviderError("semgrep", "unapproved_workspace")
        workspace = workspace.resolve()
        # Prevent source traversal through symlinks, devices, FIFOs or sockets.
        count = 0
        required_paths = set()
        try:

            def walk_error(_):
                raise ProviderError("semgrep", "unreadable_workspace")

            for base, directories, files in os.walk(
                workspace, followlinks=False, onerror=walk_error
            ):
                for name in directories + files:
                    count += 1
                    if count > 20_000:
                        raise ProviderError("semgrep", "workspace_too_large")
                    entry = Path(base) / name
                    info = entry.lstat()
                    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                        raise ProviderError("semgrep", "unsafe_workspace_entry")
                    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                        raise ProviderError("semgrep", "unsafe_workspace_entry")
                    if stat.S_ISREG(info.st_mode) and entry.suffix in self.source_suffixes:
                        required_paths.add(entry.relative_to(workspace).as_posix())
        except OSError:
            raise ProviderError("semgrep", "unreadable_workspace") from None
        version = "unavailable"
        rulesets = tuple(p.name for p in self.rules)

        def failed(code, exit_code=None):
            return ScanReport(
                ScanResult(
                    findings=[],
                    scanner_version=version,
                    ruleset_hash=self.ruleset_hash,
                    complete=False,
                ),
                diagnostics=(code,),
                exit_code=exit_code,
                rulesets=rulesets,
            )

        try:
            if any(
                not _no_symlink(p) or p.read_bytes() != data
                for p, data in zip(self.rules, self._rules_content, strict=True)
            ):
                return failed("ruleset_changed")
            with tempfile.TemporaryDirectory(prefix="proofloop-scan-") as scratch:
                scratch_path = Path(scratch)
                env = {
                    "PATH": os.defpath,
                    "HOME": scratch,
                    "XDG_CONFIG_HOME": scratch,
                    "SEMGREP_SEND_METRICS": "off",
                    "SEMGREP_ENABLE_VERSION_CHECK": "0",
                    "LANG": "C.UTF-8",
                }
                version_output = self.runner(
                    [self.executable, "--version"],
                    cwd=scratch_path,
                    env=env,
                    timeout=min(self.timeout, 10),
                )
                if version_output.returncode != 0:
                    return failed("version_failed", version_output.returncode)
                version = version_output.stdout.decode("utf-8").strip()
                if not re.fullmatch(r"\d+\.\d+\.\d+(?:[A-Za-z0-9.+-]*)?", version):
                    version = "unavailable"
                    return failed("invalid_version")
                argv = [
                    self.executable,
                    "scan",
                    "--json",
                    "--quiet",
                    "--metrics=off",
                    "--disable-version-check",
                    "--disable-nosem",
                    "--strict",
                    "--no-rewrite-rule-ids",
                    "--no-git-ignore",
                    "--oss-only",
                    "--jobs=1",
                    "--timeout=5",
                    "--max-target-bytes=1000000",
                ]
                for index, data in enumerate(self._rules_content):
                    rule = scratch_path / f"rules-{index}.yml"
                    rule.write_bytes(data)
                    argv.extend(["--config", str(rule)])
                argv.extend(["--", str(workspace)])
                output = self.runner(argv, cwd=scratch_path, env=env, timeout=self.timeout)
            raw = decode_json(output.stdout, "semgrep")
            return self._normalize(
                raw, workspace, version, output.returncode, rulesets, required_paths
            )
        except FileNotFoundError:
            return failed("scanner_or_rules_missing")
        except (OSError, UnicodeError, subprocess.SubprocessError):
            return failed("scanner_failed")
        except ProviderError as exc:
            return failed(exc.code)

    def _normalize(self, raw, workspace, version, exit_code, rulesets, required_paths):
        diagnostics = []
        findings, locations = [], []
        try:
            if not isinstance(raw, dict) or raw.get("version") != version:
                raise ValueError
            results, errors = raw["results"], raw["errors"]
            paths = raw["paths"]
            scanned = paths["scanned"]
            skipped = paths.get("skipped", [])
            if not all(isinstance(x, list) for x in [results, errors, scanned, skipped]):
                raise ValueError
            if exit_code != 0:
                diagnostics.append(f"exit_{exit_code}")
            for error in errors:
                # Raw messages can contain source/secrets; retain only safe error classification.
                code = error.get("code") if isinstance(error, dict) else None
                diagnostics.append(f"scan_error_{code}" if type(code) is int else "scan_error")
            if raw.get("skipped_rules"):
                diagnostics.append("skipped_rules")
            if skipped:
                diagnostics.append("skipped_paths")
            if not scanned:
                diagnostics.append("no_scanned_files")

            def relative(path):
                if not isinstance(path, str):
                    raise ValueError
                candidate = Path(path)
                if not candidate.is_absolute():
                    candidate = workspace / candidate
                resolved = candidate.resolve(strict=True)
                if not resolved.is_relative_to(workspace) or not _no_symlink(candidate):
                    raise ValueError
                return resolved.relative_to(workspace).as_posix()

            scanned_paths = tuple(relative(p) for p in scanned)
            skipped_paths = tuple(relative(p["path"]) for p in skipped)
            if required_paths - set(scanned_paths):
                diagnostics.append("required_sources_not_scanned")
            for result in results:
                rule_id = result["check_id"]
                if not isinstance(rule_id, str) or not re.fullmatch(
                    r"[A-Za-z0-9_.-]{1,500}", rule_id
                ):
                    raise ValueError
                path = relative(result["path"])
                if path not in scanned_paths:
                    raise ValueError
                start, end = result["start"]["line"], result["end"]["line"]
                if type(start) is not int or type(end) is not int or not 1 <= start <= end:
                    raise ValueError
                severity = result["extra"]["severity"].upper()
                severity = {
                    "ERROR": "high",
                    "WARNING": "medium",
                    "INFO": "info",
                    "LOW": "low",
                    "MEDIUM": "medium",
                    "HIGH": "high",
                    "CRITICAL": "critical",
                }[severity]
                digest = hashlib.sha256(f"{rule_id}:{path}:{start}:{end}".encode()).hexdigest()[:32]
                finding = Finding(
                    id=f"sg_{digest}", title=f"{rule_id}: {path}:{start}"[:300], severity=severity
                )
                if finding.id not in {f.id for f in findings}:
                    findings.append(finding)
                    locations.append(ScanFinding(finding.id, rule_id, path, start, end))
        except (KeyError, TypeError, ValueError, AttributeError, OSError):
            diagnostics.append("invalid_scan_output")
            scanned_paths, skipped_paths = (), ()
        return ScanReport(
            ScanResult(
                findings=findings,
                scanner_version=version,
                ruleset_hash=self.ruleset_hash,
                complete=not diagnostics,
            ),
            tuple(locations),
            tuple(diagnostics),
            scanned_paths,
            skipped_paths,
            exit_code,
            rulesets,
        )
