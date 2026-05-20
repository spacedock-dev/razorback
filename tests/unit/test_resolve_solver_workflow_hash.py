# ABOUTME: AC-2 unit tests for resolve_solver_workflow_hash (spec §8.2).
# ABOUTME: Determinism, byte-sensitivity, order-insensitivity, frame-collision immunity.

from __future__ import annotations

from pathlib import Path

from razorback.provenance.resolvers import resolve_solver_workflow_hash


def _write(root: Path, rel: str, content: bytes) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def test_returns_sha256_prefix(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", b"hello")
    out = resolve_solver_workflow_hash(tmp_path)
    assert out is not None
    assert out.startswith("sha256:")
    assert len(out) == len("sha256:") + 64


def test_deterministic_two_invocations(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", b"hello")
    _write(tmp_path, "skills/a.md", b"world")
    a = resolve_solver_workflow_hash(tmp_path)
    b = resolve_solver_workflow_hash(tmp_path)
    assert a == b


def test_byte_sensitive_one_byte_change(tmp_path: Path) -> None:
    _write(tmp_path, "a/foo.md", b"hello")
    before = resolve_solver_workflow_hash(tmp_path)
    _write(tmp_path, "a/foo.md", b"helloo")
    after = resolve_solver_workflow_hash(tmp_path)
    assert before != after


def test_order_insensitivity_equivalent_trees(tmp_path: Path) -> None:
    d1 = tmp_path / "tree1"
    d2 = tmp_path / "tree2"
    # Create same files in different filesystem order.
    _write(d1, "b/two.md", b"two")
    _write(d1, "a/one.md", b"one")
    _write(d2, "a/one.md", b"one")
    _write(d2, "b/two.md", b"two")
    assert resolve_solver_workflow_hash(d1) == resolve_solver_workflow_hash(d2)


def test_skips_dotgit_and_pycache(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", b"hello")
    baseline = resolve_solver_workflow_hash(tmp_path)
    _write(tmp_path, ".git/HEAD", b"ref: refs/heads/main\n")
    _write(tmp_path, "__pycache__/foo.cpython-312.pyc", b"\x00\x01\x02")
    _write(tmp_path, ".pytest_cache/v/cache/lastfailed", b"{}")
    _write(tmp_path, "skills/.DS_Store", b"\x00")
    after = resolve_solver_workflow_hash(tmp_path)
    assert baseline == after


def test_returns_none_on_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert resolve_solver_workflow_hash(missing) is None


def test_returns_none_when_path_is_a_file(tmp_path: Path) -> None:
    f = tmp_path / "single.md"
    f.write_bytes(b"hi")
    assert resolve_solver_workflow_hash(f) is None


def test_path_frame_collision_immunity(tmp_path: Path) -> None:
    """Path boundary framing must distinguish {ab/c: d} from {a/bc: d}."""
    d1 = tmp_path / "t1"
    d2 = tmp_path / "t2"
    _write(d1, "ab/c", b"d")
    _write(d2, "a/bc", b"d")
    assert resolve_solver_workflow_hash(d1) != resolve_solver_workflow_hash(d2)
