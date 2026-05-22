# ABOUTME: AC-2 lock — examples/drivers/dab-paper-matrix.sh still accepts --output-dir
# ABOUTME: and forwards each cell as `rk run --runs-dir <absolute path>`.

from pathlib import Path


def test_driver_accepts_output_dir_flag() -> None:
    body = Path("examples/drivers/dab-paper-matrix.sh").read_text()
    assert "--output-dir" in body, "matrix driver lost --output-dir CLI flag (AC-2)"
    assert "--runs-dir" in body, "matrix driver no longer forwards --runs-dir"


def test_driver_forwards_absolute_runs_dir() -> None:
    """OUTPUT_DIR defaults to an absolute path under REPO_ROOT/runs/goal1."""
    body = Path("examples/drivers/dab-paper-matrix.sh").read_text()
    assert 'OUTPUT_DIR="${REPO_ROOT}/runs/goal1"' in body, (
        "driver default OUTPUT_DIR no longer rooted at REPO_ROOT"
    )
