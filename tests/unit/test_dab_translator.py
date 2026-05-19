# ABOUTME: Unit tests for the DAB extensions of the harbor 0.6.6 translator.
# ABOUTME: AC-4 retry-zero; task fan-out; trial_name_map shape.

from pathlib import Path

from harbor.models.job.config import JobConfig

from razorback.compat.harbor_0_6_6 import spec_to_job_config
from razorback.spec.parse import parse_spec_text


def _make_fixture_dataset(root: Path) -> Path:
    ds = root / "query_bookreview"
    (ds / "query_dataset").mkdir(parents=True)
    (ds / "query_dataset" / "review_query.db").write_bytes(b"sqlite-stub")
    (ds / "db_config.yaml").write_text("db_clients: {}\n")
    (ds / "db_description.txt").write_text("desc")
    for qid in (1, 2, 3):
        q = ds / f"query{qid}"
        q.mkdir()
        (q / "query.json").write_text(f'"Q{qid}?"')
        (q / "validate.py").write_text(f"def validate(s): return ('{qid}' in s, 'ok')\n")
        (q / "ground_truth.csv").write_text(f"{qid}\n")
    return root


DAB_SPEC_TEMPLATE = """\
version: 1
experiment: m2-bookreview-nop
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: {data_root}
  datasets:
    - bookreview
trials: 5
"""


def test_translator_sets_retry_max_retries_zero(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _trial_map = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    # AC-4: retry-zero so first-attempt failures don't get re-counted as passes.
    assert cfg.retry.max_retries == 0


def test_translator_fans_out_one_task_per_query(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _ = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    task_names = sorted(Path(tc.path).name for tc in cfg.tasks)
    assert task_names == ["bookreview-q1", "bookreview-q2", "bookreview-q3"]
    assert isinstance(cfg, JobConfig)


def test_translator_returns_trial_name_map(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    _cfg, trial_name_map = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    assert trial_name_map == {
        "bookreview-q1": ("bookreview", 1),
        "bookreview-q2": ("bookreview", 2),
        "bookreview-q3": ("bookreview", 3),
    }


def test_translator_keeps_n_attempts_equal_to_trials(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _ = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    assert cfg.n_attempts == 5
    assert cfg.agents[0].name == "nop"


def test_translator_still_accepts_local_benchmark(tmp_path):
    """The M1 path must keep working."""
    spec = parse_spec_text(
        "version: 1\nexperiment: x\nagent:\n  kind: nop\n"
        "benchmark:\n  kind: local\n  task_paths: [examples/tasks/hello-world]\n"
        "trials: 1\n"
    )
    cfg, trial_map = spec_to_job_config(
        spec, job_name="x" * 16, jobs_dir=tmp_path / "jobs", tasks_root=tmp_path / "tasks"
    )
    assert trial_map == {}
    assert len(cfg.tasks) == 1
