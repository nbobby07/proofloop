import dataclasses
import os

import pytest

from backend.engine.patcher import (
    MAX_PATCH_BYTES,
    PatchRejected,
    SourceSnapshot,
    apply_patch,
    apply_unified_diff,
    disposable_workspace,
)


def snapshot():
    return SourceSnapshot((("app.py", b"answer = 1\n"),))


def test_deterministic_valid_and_invalid_patch():
    original = snapshot()
    patch = apply_patch(original, {"app.py": "answer = 2\n"})
    assert original.files == (("app.py", b"answer = 1\n"),)
    assert patch.patched.files == (("app.py", b"answer = 2\n"),)
    assert patch.original.sha256 != patch.patched.sha256
    assert "-answer = 1\n+answer = 2\n" in patch.unified_diff
    with pytest.raises(PatchRejected, match="syntax"):
        apply_patch(original, {"app.py": "return 2\n"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        original.files = ()


@pytest.mark.parametrize(
    "name",
    [
        "../app.py",
        "/app.py",
        "./app.py",
        "a/../app.py",
        "a//app.py",
        "a\\app.py",
        "app.py/",
        "C:/app.py",
        "a\x00.py",
        ".env.py",
        "verifier_tests/test_x.py",
        "sandbox/runner.py",
        "backend/engine/verifier.py",
        "tests/x.py",
        "policies/p.py",
        "test_app.py",
        "app_test.py",
        "requirements.txt",
        "new.py",
    ],
)
def test_reject_paths_and_unapproved_files(name):
    with pytest.raises(PatchRejected):
        apply_patch(snapshot(), {name: "x = 1\n"})


def test_reject_oversized_empty_and_non_python():
    for replacements in ({}, {"app.py": "answer = 1\n"}, {"app.py": "#" * (MAX_PATCH_BYTES + 1)}):
        with pytest.raises(PatchRejected):
            apply_patch(snapshot(), replacements)


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "fifo", "extra", "directory"])
def test_snapshot_rejects_unsafe_inventory(tmp_path, attack):
    root = tmp_path / "source"
    root.mkdir()
    target = root / "app.py"
    target.write_text("x = 1\n")
    if attack in {"symlink", "hardlink", "fifo"}:
        target.unlink()
        outside = tmp_path / "outside.py"
        outside.write_text("x = 2\n")
        if attack == "symlink":
            target.symlink_to(outside)
        elif attack == "hardlink":
            os.link(outside, target)
        else:
            os.mkfifo(target)
    elif attack == "extra":
        (root / ".env").write_text("SECRET=value")
    else:
        (root / "unapproved").mkdir()
    with pytest.raises(PatchRejected):
        SourceSnapshot.capture(root, ("app.py",))


def test_symlink_ancestor(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(PatchRejected):
        SourceSnapshot.capture(tmp_path / "link", ("app.py",))


def test_capture_immutable_and_workspace_cleanup(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "app.py").write_text("x = 1\n")
    original = SourceSnapshot.capture(root, ("app.py",))
    (root / "app.py").write_text("x = 99\n")
    with pytest.raises(RuntimeError), disposable_workspace(original, tmp_path / "runs") as path:
        assert (path / "app.py").read_bytes() == b"x = 1\n"
        assert (path / "app.py").stat().st_mode & 0o222 == 0
        raise RuntimeError("cleanup on failure")
    assert not path.exists()


@pytest.mark.parametrize(
    "old,new",
    [
        ("x=1\n", "x=2\n"),
        ("x=1", "x=2"),
        ("", "x=1\n"),
        ("x=1\n", ""),
        ("x=1\ny=2", "x=3\ny=2\n"),
        ("x=1\n" * 30, "x=2\n" + "x=1\n" * 28 + "x=3\n"),
    ],
)
def test_unified_diff_exact_roundtrip(old, new):
    original = SourceSnapshot((("app.py", old.encode()),))
    generated = apply_patch(original, {"app.py": new})
    applied = apply_unified_diff(original, generated.unified_diff, allowed_files=("app.py",))
    assert applied.patched == generated.patched
    assert applied.sha256 == generated.sha256


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.replace("-answer = 1", "-answer = 9"),
        lambda d: d.replace("app.py", "../app.py"),
        lambda d: d.replace("+++ b/app.py", "+++ b/renamed.py"),
        lambda d: d.replace("@@ -1 +1 @@", "@@ -99 +1 @@"),
        lambda d: d + d,
        lambda d: "new file mode 100644\n" + d,
        lambda d: d[:-1],
        lambda d: d.replace("@@ -1 +1 @@", "@@ -1,2 +1 @@"),
    ],
)
def test_unified_diff_rejects_malformed_or_unsafe_hunks(mutation):
    original = snapshot()
    diff = apply_patch(original, {"app.py": "answer = 2\n"}).unified_diff
    with pytest.raises(PatchRejected):
        apply_unified_diff(original, mutation(diff), allowed_files=("app.py",))


def test_unified_diff_allowlist_and_git_header():
    original = snapshot()
    diff = "diff --git a/app.py b/app.py\nindex abcd..1234 100644\n"
    diff += apply_patch(original, {"app.py": "answer = 2\n"}).unified_diff
    assert apply_unified_diff(original, diff, allowed_files=("app.py",)).unified_diff == diff
    with pytest.raises(PatchRejected):
        apply_unified_diff(original, diff, allowed_files=())
