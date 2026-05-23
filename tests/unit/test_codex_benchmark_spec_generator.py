# ABOUTME: PKG-27 generator smoke tests for Codex DAB and ade-bench matrix specs.
# ABOUTME: Keeps dry-run enumeration portable before any live Codex budget burn.

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "examples" / "drivers" / "generate-codex-benchmark-specs.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("codex_benchmark_specs", GENERATOR)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dab_dry_run_enumerates_twelve_datasets(tmp_path: Path) -> None:
    generator = _load_generator()

    rows = generator.plan_dab_specs(data_root=tmp_path / "dab-data")

    assert len(rows) == 12
    assert [row.dataset for row in rows] == [
        "agnews",
        "bookreview",
        "crmarenapro",
        "DEPS_DEV_V1",
        "GITHUB_REPOS",
        "googlelocal",
        "music_brainz_20k",
        "PANCANCER_ATLAS",
        "PATENTS",
        "stockindex",
        "stockmarket",
        "yelp",
    ]
    assert all(row.trials == 1 for row in rows)
    assert all(row.data_root == tmp_path / "dab-data" for row in rows)


def test_ade_bench_dry_run_rejects_upstream_local_task_root(tmp_path: Path) -> None:
    generator = _load_generator()
    tasks_root = tmp_path / "ade-bench" / "tasks"
    for slug in ("task_b", "task_a"):
        task_dir = tasks_root / slug
        task_dir.mkdir(parents=True)
        (task_dir / "task.yaml").write_text(f"task_id: {slug}\n")

    try:
        generator.plan_ade_bench_specs(ade_bench_root=tmp_path / "ade-bench")
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected upstream local ade-bench root rejection")

    assert "Harbor-shaped task root" in message
    assert "tasks/*/task.yaml roots are retired" in message


def test_emit_dab_codex_spec_uses_solver_v2_codex_and_harbor_dab(tmp_path: Path) -> None:
    generator = _load_generator()
    row = generator.plan_dab_specs(data_root=tmp_path / "dab-data")[1]

    spec_path = generator.emit_dab_spec(row, out_dir=tmp_path / "out")
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["agent"]["kind"] == "spacedock_solver_v2"
    assert payload["agent"]["runtime"] == "codex"
    assert payload["agent"]["model"] == "gpt-5.5"
    assert payload["agent"]["solver_workflow"] == "./examples/solver_workflows/codex-benchmark-solver"
    assert payload["benchmark"]["kind"] == "harbor_dab"
    assert payload["benchmark"]["datasets"] == ["bookreview"]
    assert payload["benchmark"]["data_root"] == str(tmp_path / "dab-data")
    assert payload["benchmark"]["workspace_variant"] == "direct-structured"
    assert payload["benchmark"]["hints"] is False
    assert payload["trials"] == 1
    assert "reasoning_effort" not in payload["agent"]


def test_codex_ade_dbt_repair_workflow_is_checked_in() -> None:
    workflow_readme = (
        REPO_ROOT / "examples" / "solver_workflows" / "codex-ade-dbt-repair" / "README.md"
    )

    assert workflow_readme.is_file()
    text = workflow_readme.read_text().lower()
    assert "dbt" in text
    assert "repair" in text
    assert "repaired project state" in text
    assert "answers.json" not in text


def test_emit_specs_allow_solver_workflow_selection(tmp_path: Path) -> None:
    generator = _load_generator()
    dab_row = generator.plan_dab_specs(data_root=tmp_path / "dab-data")[0]
    ade_tasks_root = tmp_path / "harbor-data" / "ade-bench"
    ade_task_dir = ade_tasks_root / "example001"
    ade_task_dir.mkdir(parents=True)
    (ade_task_dir / "task.toml").write_text('schema_version = "1.2"\n')
    ade_row = generator.plan_ade_bench_specs(ade_bench_root=ade_tasks_root)[0]

    dab_spec_path = generator.emit_dab_spec(
        dab_row,
        out_dir=tmp_path / "out" / "dab",
        solver_workflow="./examples/solver_workflows/codex-benchmark-solver",
    )
    ade_spec_path = generator.emit_ade_bench_spec(
        ade_row,
        out_dir=tmp_path / "out" / "ade",
        solver_workflow="./examples/solver_workflows/codex-ade-dbt-repair",
    )

    dab_payload = yaml.safe_load(dab_spec_path.read_text())
    ade_payload = yaml.safe_load(ade_spec_path.read_text())
    assert (
        dab_payload["agent"]["solver_workflow"]
        == "./examples/solver_workflows/codex-benchmark-solver"
    )
    assert (
        ade_payload["agent"]["solver_workflow"]
        == "./examples/solver_workflows/codex-ade-dbt-repair"
    )


def test_checked_in_dab_smoke_spec_uses_structured_workspace_without_hints() -> None:
    spec_path = REPO_ROOT / "examples" / "specs" / "codex-dab-smoke.yaml"
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["benchmark"]["kind"] == "harbor_dab"
    assert payload["benchmark"]["datasets"] == ["bookreview"]
    assert payload["benchmark"]["workspace_variant"] == "direct-structured"
    assert payload["benchmark"]["hints"] is False


def test_emit_dab_codex_spec_allows_model_override(tmp_path: Path) -> None:
    generator = _load_generator()
    row = generator.plan_dab_specs(data_root=tmp_path / "dab-data")[0]

    spec_path = generator.emit_dab_spec(
        row, out_dir=tmp_path / "out", model="gpt-future-codex"
    )
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["agent"]["model"] == "gpt-future-codex"


def test_emit_dab_codex_spec_allows_reasoning_effort(tmp_path: Path) -> None:
    generator = _load_generator()
    row = generator.plan_dab_specs(data_root=tmp_path / "dab-data")[0]

    spec_path = generator.emit_dab_spec(
        row, out_dir=tmp_path / "out", reasoning_effort="xhigh"
    )
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["agent"]["reasoning_effort"] == "xhigh"


def test_cli_can_emit_reasoning_effort_when_requested(
    tmp_path: Path, monkeypatch
) -> None:
    generator = _load_generator()
    monkeypatch.setattr(
        generator,
        "plan_dab_specs",
        lambda *, data_root: [
            generator.DabSpecRow(dataset="bookreview", data_root=data_root, trials=1)
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(GENERATOR),
            "--benchmark",
            "dab",
            "--dab-data-root",
            str(tmp_path / "dab-data"),
            "--out-root",
            str(tmp_path / "specs"),
            "--reasoning-effort",
            "xhigh",
            "--write",
        ],
    )

    assert generator.main() == 0

    payload = yaml.safe_load((tmp_path / "specs" / "dab" / "bookreview.yaml").read_text())
    assert payload["agent"]["reasoning_effort"] == "xhigh"


def test_cli_can_emit_custom_ade_solver_workflow(tmp_path: Path, monkeypatch) -> None:
    generator = _load_generator()
    monkeypatch.setattr(
        generator,
        "plan_ade_bench_specs",
        lambda *, ade_bench_root: [
            generator.AdeBenchSpecRow(
                task_slug="example001",
                tasks_root=ade_bench_root,
                trials=1,
            )
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(GENERATOR),
            "--benchmark",
            "ade-bench",
            "--ade-bench-root",
            str(tmp_path / "ade-bench"),
            "--out-root",
            str(tmp_path / "specs"),
            "--solver-workflow",
            "./examples/solver_workflows/codex-ade-dbt-repair",
            "--write",
        ],
    )

    assert generator.main() == 0

    payload = yaml.safe_load(
        (tmp_path / "specs" / "ade-bench" / "example001.yaml").read_text()
    )
    assert (
        payload["agent"]["solver_workflow"]
        == "./examples/solver_workflows/codex-ade-dbt-repair"
    )


def test_cli_can_emit_dab_workspace_and_hints_variants(
    tmp_path: Path, monkeypatch
) -> None:
    generator = _load_generator()
    monkeypatch.setattr(
        generator,
        "plan_dab_specs",
        lambda *, data_root: [
            generator.DabSpecRow(dataset="bookreview", data_root=data_root, trials=1)
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(GENERATOR),
            "--benchmark",
            "dab",
            "--dab-data-root",
            str(tmp_path / "dab-data"),
            "--out-root",
            str(tmp_path / "specs"),
            "--workspace-variant",
            "spacedock",
            "--hints",
            "--write",
        ],
    )

    assert generator.main() == 0

    payload = yaml.safe_load((tmp_path / "specs" / "dab" / "bookreview.yaml").read_text())
    assert payload["benchmark"]["workspace_variant"] == "spacedock"
    assert payload["benchmark"]["hints"] is True


def test_cli_can_explicitly_disable_dab_hints(tmp_path: Path, monkeypatch) -> None:
    generator = _load_generator()
    monkeypatch.setattr(
        generator,
        "plan_dab_specs",
        lambda *, data_root: [
            generator.DabSpecRow(dataset="bookreview", data_root=data_root, trials=1)
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(GENERATOR),
            "--benchmark",
            "dab",
            "--dab-data-root",
            str(tmp_path / "dab-data"),
            "--out-root",
            str(tmp_path / "specs"),
            "--no-hints",
            "--write",
        ],
    )

    assert generator.main() == 0

    payload = yaml.safe_load((tmp_path / "specs" / "dab" / "bookreview.yaml").read_text())
    assert payload["benchmark"]["workspace_variant"] == "direct-structured"
    assert payload["benchmark"]["hints"] is False


def test_display_path_handles_relative_and_external_out_roots(tmp_path: Path) -> None:
    generator = _load_generator()

    assert (
        generator._display_path(Path("runs/goal3/specs/dab/bookreview.yaml"))
        == "runs/goal3/specs/dab/bookreview.yaml"
    )
    assert (
        generator._display_path(
            generator.REPO_ROOT / "runs" / "goal3" / "specs" / "dab" / "agnews.yaml"
        )
        == "runs/goal3/specs/dab/agnews.yaml"
    )
    external = tmp_path / "specs" / "dab" / "agnews.yaml"
    assert generator._display_path(external) == str(external.resolve())


def test_emit_ade_bench_codex_spec_never_uses_local_task_entry(tmp_path: Path) -> None:
    generator = _load_generator()
    tasks_root = tmp_path / "harbor-data" / "ade-bench"
    task_dir = tasks_root / "example001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text('schema_version = "1.2"\n')
    row = generator.plan_ade_bench_specs(ade_bench_root=tasks_root)[0]

    spec_path = generator.emit_ade_bench_spec(row, out_dir=tmp_path / "out")
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["agent"]["kind"] == "spacedock_solver_v2"
    assert payload["agent"]["runtime"] == "codex"
    assert payload["agent"]["model"] == "gpt-5.5"
    assert payload["benchmark"]["kind"] == "ade-bench"
    assert payload["benchmark"]["tasks_root"] == str(tasks_root)
    assert payload["benchmark"]["tasks"] == ["example001"]
    assert "ade_bench_root" not in payload["benchmark"]
    assert {"slug": "example001"} not in payload["benchmark"]["tasks"]
    assert payload["trials"] == 1


def test_emit_ade_bench_codex_spec_uses_harbor_shaped_task_root(tmp_path: Path) -> None:
    generator = _load_generator()
    ade_bench_root = tmp_path / "harbor-data" / "ade-bench"
    for slug in ("task_b", "task_a"):
        task_dir = ade_bench_root / slug
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text(f'name = "{slug}"\n')

    rows = generator.plan_ade_bench_specs(ade_bench_root=ade_bench_root)
    spec_path = generator.emit_ade_bench_spec(
        rows[0],
        out_dir=tmp_path / "out",
        solver_workflow="./examples/solver_workflows/codex-ade-dbt-repair",
    )
    payload = yaml.safe_load(spec_path.read_text())

    assert [row.task_slug for row in rows] == ["task_a", "task_b"]
    assert payload["agent"]["solver_workflow"] == "./examples/solver_workflows/codex-ade-dbt-repair"
    assert payload["benchmark"]["kind"] == "ade-bench"
    assert payload["benchmark"]["tasks_root"] == str(ade_bench_root)
    assert payload["benchmark"]["tasks"] == ["task_a"]
    assert "ade_bench_root" not in payload["benchmark"]


def test_plan_ade_bench_specs_rejects_unknown_root_shape(tmp_path: Path) -> None:
    generator = _load_generator()
    missing_root = tmp_path / "missing"

    try:
        generator.plan_ade_bench_specs(ade_bench_root=missing_root)
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")

    assert "Harbor-shaped task root" in message
    assert "tasks/*/task.yaml roots are retired" in message
    assert str(missing_root) in message


def test_emit_dab_codex_spec_allows_workspace_and_hints_variants(tmp_path: Path) -> None:
    generator = _load_generator()
    row = generator.plan_dab_specs(data_root=tmp_path / "dab-data")[0]

    spec_path = generator.emit_dab_spec(
        row,
        out_dir=tmp_path / "out",
        workspace_variant="spacedock",
        hints=True,
    )
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["benchmark"]["workspace_variant"] == "spacedock"
    assert payload["benchmark"]["hints"] is True
