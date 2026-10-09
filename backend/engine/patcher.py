"""Pure-data patch admission; no target code is ever imported or executed here."""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_PATCH_BYTES = 512 * 1024
FORBIDDEN_PARTS = {
    ".git",
    ".ssh",
    ".aws",
    "tests",
    "verifier_tests",
    "sandbox",
    "backend",
    "policies",
    "node_modules",
    "__pycache__",
}


class PatchRejected(ValueError):
    """Untrusted patch or workspace violates the admission policy."""


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def safe_path(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or "\\" in name
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise PatchRejected("Invalid relative file path")
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or path.as_posix() != name
        or any(part in {"", ".", ".."} or ":" in part for part in name.split("/"))
    ):
        raise PatchRejected("Absolute, noncanonical, or traversing file path")
    return name


def source_path(name: str) -> str:
    safe_path(name)
    parts = PurePosixPath(name).parts
    if any(p.startswith(".") or p.lower() in FORBIDDEN_PARTS for p in parts):
        raise PatchRejected("Protected path")
    if not name.endswith(".py") or any(
        p.lower().startswith("test_") or p.lower().endswith("_test.py") for p in parts
    ):
        raise PatchRejected("Only approved Python source files may be patched")
    return name


def checked_root(root: Path) -> Path:
    root = Path(os.path.abspath(root))
    for path in (root, *root.parents):
        if path.is_symlink():
            raise PatchRejected("Symlink in workspace path")
    if not root.is_dir():
        raise PatchRejected("Workspace must be a directory")
    return root


def read_tree(root: Path, names: tuple[str, ...]) -> tuple[tuple[str, bytes], ...]:
    """Read an exact curated tree, excluding every unapproved file (including secrets)."""
    root = checked_root(root)
    if not names or len(names) != len(set(names)):
        raise PatchRejected("Empty or duplicate file allowlist")
    for name in names:
        safe_path(name)
    expected = set(names)
    directories = {str(p) for n in names for p in PurePosixPath(n).parents if str(p) != "."}
    found: dict[str, bytes] = {}
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            path = Path(directory) / name
            if path.is_symlink() or path.relative_to(root).as_posix() not in directories:
                raise PatchRejected("Unexpected directory or symlink")
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative not in expected:
                raise PatchRejected("Unexpected file in curated workspace")
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                        raise PatchRejected("Symlink, hardlink, or special file")
                    data = stream.read(MAX_FILE_BYTES + 1)
                    after = os.fstat(stream.fileno())
                    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ino,
                    ):
                        raise PatchRejected("File changed during snapshot")
            except OSError as exc:
                raise PatchRejected("Unable to safely read workspace") from exc
            total += len(data)
            if len(data) > MAX_FILE_BYTES or total > MAX_SOURCE_BYTES:
                raise PatchRejected("Workspace size limit exceeded")
            found[relative] = data
    if set(found) != expected:
        raise PatchRejected("Required file missing")
    return tuple(sorted(found.items()))


def validate_python(files: tuple[tuple[str, bytes], ...]) -> None:
    for name, data in files:
        try:
            text = data.decode("utf-8")
            ast.parse(text, filename=name)
            # compile catches invalid contextual constructs (e.g. return outside a function).
            compile(text, name, "exec", dont_inherit=True)
        except (UnicodeError, SyntaxError, ValueError, RecursionError) as exc:
            raise PatchRejected(f"Invalid Python syntax in {name}") from exc


@dataclass(frozen=True)
class SourceSnapshot:
    """Immutable bytes, independent of future checkout mutations; hash is content-derived."""

    files: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.files, tuple) or not self.files:
            raise PatchRejected("Snapshot must contain immutable file records")
        names = []
        total = 0
        for record in self.files:
            if not isinstance(record, tuple) or len(record) != 2:
                raise PatchRejected("Invalid snapshot record")
            name, data = record
            source_path(name)
            if not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES:
                raise PatchRejected("Invalid source bytes")
            names.append(name)
            total += len(data)
        if names != sorted(set(names)) or total > MAX_SOURCE_BYTES:
            raise PatchRejected("Invalid source inventory")
        validate_python(self.files)

    @property
    def sha256(self) -> str:
        return digest([(name, hashlib.sha256(data).hexdigest()) for name, data in self.files])

    @classmethod
    def capture(cls, root: Path, allowed_files: tuple[str, ...]) -> SourceSnapshot:
        for name in allowed_files:
            source_path(name)
        return cls(read_tree(root, allowed_files))


@dataclass(frozen=True)
class PreparedPatch:
    original: SourceSnapshot
    patched: SourceSnapshot
    unified_diff: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.unified_diff.encode()).hexdigest()


def apply_patch(original: SourceSnapshot, replacements: Mapping[str, str]) -> PreparedPatch:
    """Admit full-file replacements, NOT model-controlled shell commands or patch tools."""
    if not replacements:
        raise PatchRejected("Empty patch")
    files = dict(original.files)
    size = 0
    for name, text in replacements.items():
        source_path(name)
        if name not in files or not isinstance(text, str):
            raise PatchRejected("Patch can only replace allowlisted existing source files")
        data = text.encode("utf-8")
        size += len(data)
        if len(data) > MAX_FILE_BYTES or size > MAX_PATCH_BYTES:
            raise PatchRejected("Patch size limit exceeded")
        files[name] = data
    patched = SourceSnapshot(tuple(sorted(files.items())))
    chunks = []
    for name, before in original.files:
        after = files[name]
        if before == after:
            continue
        for line in difflib.unified_diff(
            before.decode().splitlines(keepends=True),
            after.decode().splitlines(keepends=True),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
        ):
            chunks.append(
                line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            )
    diff = "".join(chunks)
    if not diff or len(diff.encode()) > MAX_PATCH_BYTES:
        raise PatchRejected("Empty or oversized unified diff")
    return PreparedPatch(original, patched, diff)


def materialize(files: tuple[tuple[str, bytes], ...], root: Path) -> None:
    root.mkdir(mode=0o700)
    for name, data in files:
        destination = root / safe_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o444)
    for directory, _, _ in os.walk(root, topdown=False):
        Path(directory).chmod(0o555)


def remove_readonly(root: Path) -> None:
    for directory, _, _ in os.walk(root):
        Path(directory).chmod(0o700)


@contextmanager
def disposable_workspace(snapshot: SourceSnapshot, workspace_parent: Path) -> Iterator[Path]:
    """Fresh read-only mount input per attempt; always remove it after execution."""
    workspace_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    checked_root(workspace_parent)
    with tempfile.TemporaryDirectory(prefix="proofloop-", dir=workspace_parent) as temporary:
        root = Path(temporary) / "source"
        try:
            materialize(snapshot.files, root)
            yield root
        finally:
            remove_readonly(Path(temporary))


def apply_unified_diff(
    original: SourceSnapshot, diff: str, *, allowed_files: tuple[str, ...]
) -> PreparedPatch:
    """Apply strict, exact-context unified diffs without shell/git, fuzz, or path rewriting.

    No additions, deletions, renames, mode changes, binary patches, duplicate files,
    or ambiguous headers. The admitted original diff bytes remain the patch identity.
    """
    import re

    if not isinstance(diff, str) or not diff or len(diff.encode()) > MAX_PATCH_BYTES:
        raise PatchRejected("Empty or oversized unified diff")
    lines = diff.splitlines(keepends=True)
    if any(not line.endswith("\n") for line in lines):
        raise PatchRejected("Unified diff must end each record with a newline")
    source = dict(original.files)
    allowed = set(allowed_files)
    for name in allowed:
        source_path(name)
    replacements = {}
    cursor = 0
    while cursor < len(lines):
        git_name = None
        if lines[cursor].startswith("diff --git "):
            match = re.fullmatch(r"diff --git a/([^\s]+) b/([^\s]+)\n", lines[cursor])
            if not match or match[1] != match[2]:
                raise PatchRejected("Invalid diff file header")
            git_name = match[1]
            cursor += 1
            if cursor < len(lines) and lines[cursor].startswith("index "):
                if not re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?\n", lines[cursor]):
                    raise PatchRejected("Unsupported diff index or file mode")
                cursor += 1
        if cursor + 1 >= len(lines) or not lines[cursor].startswith("--- a/"):
            raise PatchRejected("Expected original file header")
        name = lines[cursor][6:-1]
        source_path(name)
        if lines[cursor + 1] != f"+++ b/{name}\n" or (git_name and git_name != name):
            raise PatchRejected("Renamed or ambiguous patch path")
        if name not in allowed or name not in source or name in replacements:
            raise PatchRejected("Unexpected or duplicate patched file")
        cursor += 2
        old_lines = source[name].decode().splitlines(keepends=True)
        output = []
        consumed = 0
        hunks = 0
        while cursor < len(lines) and lines[cursor].startswith("@@"):
            match = re.fullmatch(
                r"@@ -(\d{1,7})(?:,(\d{1,7}))? \+(\d{1,7})(?:,(\d{1,7}))? @@[^\n]*\n", lines[cursor]
            )
            if not match:
                raise PatchRejected("Invalid hunk header")
            old_start, old_count, new_start, new_count = (
                int(match[1]),
                int(match[2] or 1),
                int(match[3]),
                int(match[4] or 1),
            )
            position = old_start - 1 if old_count else old_start
            new_position = new_start - 1 if new_count else new_start
            if position < consumed or position > len(old_lines):
                raise PatchRejected("Overlapping or out-of-range hunk")
            output.extend(old_lines[consumed:position])
            if new_position != len(output):
                raise PatchRejected("Hunk new-source position mismatch")
            cursor += 1
            records = []
            old_seen = new_seen = 0
            while cursor < len(lines) and (old_seen < old_count or new_seen < new_count):
                line = lines[cursor]
                if line[0] not in " +-":
                    raise PatchRejected("Invalid hunk record")
                prefix, value = line[0], line[1:]
                cursor += 1
                if cursor < len(lines) and lines[cursor] == "\\ No newline at end of file\n":
                    value = value[:-1]
                    cursor += 1
                records.append((prefix, value))
                old_seen += prefix in " -"
                new_seen += prefix in " +"
            if (old_seen, new_seen) != (old_count, new_count):
                raise PatchRejected("Truncated or inconsistent hunk")
            consumed = position
            for prefix, value in records:
                if prefix in " -":
                    if consumed >= len(old_lines) or old_lines[consumed] != value:
                        raise PatchRejected("Hunk does not exactly match original source")
                    consumed += 1
                if prefix in " +":
                    output.append(value)
            hunks += 1
        if not hunks:
            raise PatchRejected("File patch has no hunks")
        output.extend(old_lines[consumed:])
        replacements[name] = "".join(output)
    prepared = apply_patch(original, replacements)
    return PreparedPatch(prepared.original, prepared.patched, diff)
