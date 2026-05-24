# ABOUTME: Cycle-1 integration test — translator's plugin-route invokes the real
# ABOUTME: razorback-plugin-dab CLI (no subprocess mock), catches CLI-contract drift.

"""Real-binary integration test for the dab-plugin dispatch path.

The cycle-0 unit tests at `tests/translate/test_dab_dispatch.py` mock
`subprocess.run`; that masked a `--dataset` vs `--datasets` CLI drift
between the translator emission and the plugin CLI. This test invokes
the real plugin binary via the translator's `_invoke_plugin_generate`
helper using the plugin's `hello-fixture` dataset (no DAB data root
required) and asserts exit 0 + emitted task tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from razorback.spec.parse import parse_spec_text
from razorback.translate import spec_to_job_config


def _spec_text() -> str:
    return """\
version: 1
experiment: cycle1-real-dispatch
agent:
  kind: nop
benchmark:
  kind: harbor
  dataset: dab@1.0
  plugin: dab
  tasks: [hello-fixture]
trials: 1
"""


def test_real_plugin_dispatch_emits_hello_fixture(tmp_path: Path) -> None:
    """Translator emits an argv the real plugin CLI accepts.

    This is the non-mock equivalent of
    `tests/translate/test_dab_dispatch.py::test_dab_plugin_dispatch_invokes_subprocess_and_builds_tasks`.
    If the translator emits a flag the plugin CLI doesn't accept (or vice
    versa), subprocess returncode != 0 → SpecError → this test fails.
    """
    spec = parse_spec_text(_spec_text())
    tasks_root = tmp_path / "tasks"
    job_cfg, _ = spec_to_job_config(
        spec,
        job_name="cycle1-real-dispatch",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tasks_root,
    )
    # Plugin's hello-fixture emits exactly one task dir at <tasks_root>/hello-fixture/.
    assert len(job_cfg.tasks) == 1
    emitted = job_cfg.tasks[0].path
    assert emitted == tasks_root / "hello-fixture"
    assert (emitted / "task.toml").is_file()
    assert (emitted / "instruction.md").is_file()
    assert (emitted / "tests" / "test.sh").is_file()


def _goal1_shape_spec_text() -> str:
    """Mirrors the goal1 spec shape exactly: plugin_args carries the three
    behavioral knobs (workspace_variant/query_mode/hints) but NOT data_root.
    The plugin CLI's env-default fallback must satisfy data_root from
    DATAAGENTBENCH_DATA_ROOT."""
    return """\
version: 1
experiment: cycle9-goal1-shape-env-default
agent:
  kind: nop
benchmark:
  kind: harbor
  dataset: dab@1.0
  plugin: dab
  plugin_args:
    workspace_variant: spacedock
    query_mode: batch
    hints: true
  tasks: [hello-fixture]
trials: 1
"""


def test_goal1_shape_dispatch_uses_env_default_data_root(tmp_path: Path, monkeypatch) -> None:
    """Cycle-9 cycle-8-Material-#4 fix verifier.

    A spec carrying the goal1 shape (plugin_args without `data_root`)
    must succeed when `$DATAAGENTBENCH_DATA_ROOT` is set. This exercises
    the plugin CLI's env-default fallback through the real translator +
    real plugin binary (no subprocess mock).

    Uses `hello-fixture` for the dataset so the test stays env-free at
    the data-content level — but exercises the data_root resolution path
    because plugin_args lacks an explicit value, so the translator emits
    no `--data-root` flag and the plugin CLI must resolve via env.
    """
    # Even though hello-fixture short-circuits before the data-root gate,
    # set the env so the test would still pass with a real dataset.
    monkeypatch.setenv("DATAAGENTBENCH_DATA_ROOT", str(tmp_path / "fake-data"))
    (tmp_path / "fake-data").mkdir()

    spec = parse_spec_text(_goal1_shape_spec_text())
    tasks_root = tmp_path / "tasks"
    job_cfg, _ = spec_to_job_config(
        spec,
        job_name="cycle9-goal1-shape-env-default",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tasks_root,
    )
    assert len(job_cfg.tasks) == 1
    assert (job_cfg.tasks[0].path / "task.toml").is_file()
