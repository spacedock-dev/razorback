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
