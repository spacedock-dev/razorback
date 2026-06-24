# ABOUTME: AC-3 — aggregate_summary stratifies CANONICAL swe-bench-pro task slugs
# ABOUTME: (containing __, exceeding the 32-char join window) into distinct per-task
# ABOUTME: query cells. RED on the dir-name join; GREEN via config.json task-path
# ABOUTME: resolution. Regression-guards short __-free slugs (dabstep/spider2/ade).
import json
import re
from pathlib import Path

from harbor.models.trial.config import TaskConfig, TrialConfig

from razorback.runs.aggregate import aggregate_summary


def _view_name(slug: str) -> str:
    # Mirrors harbor_tasks/materialize.py:_view_name (kind-task, sanitized, [:160]).
    raw = f"swe-bench-pro-{slug}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-._")[:160] or "task-view"


def _build_swe_run(tmp_path: Path, slugs_rewards: list[tuple[str, float]]) -> Path:
    """Synthetic run dir using REAL harbor trial naming + the REAL per-trial
    config.json harbor persists (trial.py:934). Each view dir carries a
    view_manifest.json sidecar; each trial dir carries result.json + config.json
    whose task.path points at its view dir."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for slug, reward in slugs_rewards:
        view = run_dir / "tasks" / _view_name(slug)
        view.mkdir(parents=True)
        (view / "view_manifest.json").write_text(
            json.dumps(
                {
                    "benchmark_kind": "swe-bench-pro",
                    "benchmark_task_id": slug,
                    "view_mode": "copy",
                }
            )
        )
        # REAL harbor TrialConfig: trial_name via generate_trial_name, task.path
        # = the view dir. This is exactly what harbor writes to config.json.
        tc = TrialConfig(task=TaskConfig(path=str(view)))
        trial = run_dir / tc.trial_name
        trial.mkdir()
        (trial / "result.json").write_text(
            json.dumps({"verifier_result": {"rewards": {"reward": reward}}})
        )
        (trial / "config.json").write_text(tc.model_dump_json(indent=4))
    return run_dir


def test_aggregator_stratifies_canonical_swe_bench_pro_slugs(tmp_path):
    """Canonical project-prefixed swe-bench-pro slugs (with __, > 18 task-id
    chars) land in DISTINCT swe-bench-pro query cells, never the `default`
    collapse, and -11099/-11098 do NOT collide. RED on the dir-name join."""
    run_dir = _build_swe_run(
        tmp_path,
        [
            ("astropy__astropy-7166", 1.0),
            ("django__django-11099", 0.0),
            ("django__django-11098", 1.0),
        ],
    )

    aggregate_summary(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())
    datasets = summary["datasets"]

    assert "swe-bench-pro" in datasets, (
        f"expected swe-bench-pro stratum, got {sorted(datasets)}"
    )
    assert "default" not in datasets, (
        f"canonical __ slugs collapsed to default: {datasets.get('default')}"
    )
    cells = datasets["swe-bench-pro"]["queries"]
    assert datasets["swe-bench-pro"]["n_queries"] == 3, datasets["swe-bench-pro"]
    cell_ids = {c["query_id"] for c in cells}
    assert cell_ids == {
        "astropy__astropy-7166",
        "django__django-11099",
        "django__django-11098",
    }, f"collision/mis-cut: cells={cell_ids}"
    kinds = {t["stratum"].get("benchmark_kind") for t in summary["trials"]}
    assert kinds == {"swe-bench-pro"}, kinds


def test_short_dunderless_slugs_still_stratify_via_fallback(tmp_path):
    """Regression guard: short, __-free slugs that DON'T carry a config.json
    task path still resolve through the retained dir-name join (the
    dabstep/spider2/ade path). No config.json written here on purpose."""
    run_dir = tmp_path / "legacy"
    run_dir.mkdir()
    for view_name, slug, reward in [
        ("ade-bench-adebench-fixture-001", "adebench-fixture-001", 1.0),
        ("spider2-dbt-spider2-fixture-001", "spider2-fixture-001", 0.0),
    ]:
        view = run_dir / "tasks" / view_name
        view.mkdir(parents=True)
        kind = "ade-bench" if view_name.startswith("ade") else "spider2-dbt"
        (view / "view_manifest.json").write_text(
            json.dumps({"benchmark_kind": kind, "benchmark_task_id": slug})
        )
        trial_prefix = view_name[:32].rstrip("_-")
        trial = run_dir / f"{trial_prefix}__deadbee"
        trial.mkdir()
        (trial / "result.json").write_text(
            json.dumps({"verifier_result": {"rewards": {"reward": reward}}})
        )
    aggregate_summary(run_dir)
    datasets = json.loads((run_dir / "summary.json").read_text())["datasets"]
    assert set(datasets) == {"ade-bench", "spider2-dbt"}, sorted(datasets)
    assert "default" not in datasets


def test_short_dunderless_slugs_stratify_via_config_first_path(tmp_path):
    """Backward-compat lock-in: short, __-free slugs that DO carry a real
    config.json resolve through the NEW config-first path (not the fallback)
    to the SAME {dataset, query_id} identity the legacy dir-name join would.
    Permanent version of Codex's one-off old==new probe for spider2-dbt/ade."""
    run_dir = tmp_path / "config_first"
    run_dir.mkdir()
    expected = {
        "spider2-dbt": "spider2-fixture-001",
        "ade-bench": "adebench-fixture-001",
    }
    for kind, slug, reward in [
        ("spider2-dbt", "spider2-fixture-001", 0.0),
        ("ade-bench", "adebench-fixture-001", 1.0),
    ]:
        view = run_dir / "tasks" / f"{kind}-{slug}"
        view.mkdir(parents=True)
        (view / "view_manifest.json").write_text(
            json.dumps({"benchmark_kind": kind, "benchmark_task_id": slug})
        )
        # REAL per-trial config.json — drives the config-FIRST resolution path.
        tc = TrialConfig(task=TaskConfig(path=str(view)))
        trial = run_dir / tc.trial_name
        trial.mkdir()
        (trial / "result.json").write_text(
            json.dumps({"verifier_result": {"rewards": {"reward": reward}}})
        )
        (trial / "config.json").write_text(tc.model_dump_json(indent=4))

    aggregate_summary(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())
    datasets = summary["datasets"]
    assert set(datasets) == {"spider2-dbt", "ade-bench"}, sorted(datasets)
    assert "default" not in datasets
    for kind, slug in expected.items():
        cells = datasets[kind]["queries"]
        assert datasets[kind]["n_queries"] == 1, datasets[kind]
        assert {c["query_id"] for c in cells} == {slug}, (kind, cells)
    by_kind = {t["stratum"].get("benchmark_kind") for t in summary["trials"]}
    assert by_kind == {"spider2-dbt", "ade-bench"}, by_kind
