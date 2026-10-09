"""Admission checks only: applying a proposal remains the trusted patcher's job."""

import re
from collections.abc import Collection
from pathlib import PurePosixPath

from backend.providers.contracts import SourceSnapshot
from backend.providers.errors import ProviderError

PROTECTED_PARTS = {
    "tests",
    "test",
    "verifier_tests",
    "policies",
    "policy",
    "sandbox",
    "providers",
    "engine",
    ".git",
    ".github",
    "contracts",
}


def mutable_path(path: str) -> bool:
    if not isinstance(path, str) or not path or "\\" in path or re.search(r"\s|[\x00-\x1f]", path):
        return False
    parsed = PurePosixPath(path)
    parts = path.split("/")
    if parsed.is_absolute() or any(p in {"", ".", ".."} for p in parts):
        return False
    lower = [p.lower() for p in parts]
    name = lower[-1]
    return not (
        set(lower) & PROTECTED_PARTS
        or name.startswith(("test_", ".env"))
        or name.endswith("_test.py")
        or name
        in {
            "security.md",
            "agents.md",
            "pyproject.toml",
            "package.json",
            "package-lock.json",
            "requirements.txt",
            "requirements.lock",
            "dockerfile",
        }
    )


def validate_patch(diff: str, source: SourceSnapshot, allowed: Collection[str]) -> None:
    """Accept modification-only unified diffs matching the approved snapshot.

    No new/deleted files, renames, binary patches, mode changes or ambiguous paths.
    """

    def reject():
        raise ProviderError("openai", "unsafe_patch")

    try:
        size = len(diff.encode())
    except UnicodeError:
        reject()
    if size > 200_000 or "\x00" in diff or "\r" in diff:
        reject()
    lines = diff.splitlines(keepends=True)
    if any(not line.endswith("\n") for line in lines):
        reject()
    index = 0
    changed = set()
    while index < len(lines):
        if lines[index].startswith("diff --git "):
            match = re.fullmatch(r"diff --git a/(\S+) b/(\S+)\n", lines[index])
            if not match or match[1] != match[2]:
                reject()
            git_path = match[1]
            index += 1
            if index < len(lines) and lines[index].startswith("index "):
                if not re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?\n", lines[index]):
                    reject()
                index += 1
        else:
            git_path = None
        if index + 1 >= len(lines):
            reject()
        old = re.fullmatch(r"--- a/(\S+)\n", lines[index])
        new = re.fullmatch(r"\+\+\+ b/(\S+)\n", lines[index + 1])
        if not old or not new or old[1] != new[1] or (git_path and git_path != old[1]):
            reject()
        path = old[1]
        if (
            path in changed
            or path not in allowed
            or path not in source.files
            or not mutable_path(path)
        ):
            reject()
        changed.add(path)
        original = source.files[path].splitlines(keepends=True)
        index += 2
        previous_end = 0
        delta = 0
        hunks = 0
        edited = False
        while index < len(lines) and lines[index].startswith("@@ "):
            header = re.fullmatch(
                r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n", lines[index]
            )
            if not header:
                reject()
            old_start, old_count = int(header[1]), int(header[2] or 1)
            new_start, new_count = int(header[3]), int(header[4] or 1)
            offset = old_start - 1 if old_count else old_start
            new_offset = new_start - 1 if new_count else new_start
            if offset < previous_end or new_offset != offset + delta or offset > len(original):
                reject()
            index += 1
            old_lines, new_lines = [], []
            while index < len(lines) and lines[index][:1] in {" ", "+", "-", "\\"}:
                if lines[index].startswith("--- a/"):
                    break
                line = lines[index]
                if line.startswith("\\"):
                    reject()
                prefix, content = line[0], line[1:]
                index += 1
                if index < len(lines) and lines[index].startswith("\\ No newline at end of file"):
                    if lines[index].rstrip("\n") != "\\ No newline at end of file":
                        reject()
                    content = content.removesuffix("\n")
                    index += 1
                if prefix in {" ", "-"}:
                    old_lines.append(content)
                if prefix in {" ", "+"}:
                    new_lines.append(content)
                edited |= prefix in {"+", "-"}
            if len(old_lines) != old_count or len(new_lines) != new_count:
                reject()
            if original[offset : offset + old_count] != old_lines:
                reject()
            previous_end = offset + old_count
            delta += new_count - old_count
            hunks += 1
        if not hunks or not edited:
            reject()
    if not changed:
        reject()
