# ABOUTME: Translator fans out to all 12 DAB datasets — generalizes M2's bookreview-only path.

from pathlib import Path

from razorback.compat.harbor_0_6_6 import spec_to_job_config
from razorback.spec.parse import parse_spec_text


TWELVE = [
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


def _make_fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    for slug in TWELVE:
        ds = root / f"query_{slug}"
        (ds / "query_dataset").mkdir(parents=True)
        (ds / "query_dataset" / "review_query.db").write_bytes(b"sqlite-stub")
        (ds / "db_config.yaml").write_text("db_clients: {}\n")
        (ds / "db_description.txt").write_text("desc")
        q = ds / "query1"
        q.mkdir()
        (q / "query.json").write_text('"Q1?"')
        (q / "validate.py").write_text("def validate(s): return ('1' in s, 'ok')\n")
        (q / "ground_truth.csv").write_text("1\n")
    return root


SPEC_TEMPLATE = """\
version: 1
experiment: m5-twelve
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: {data_root}
  datasets:
    - agnews
    - bookreview
    - crmarenapro
    - DEPS_DEV_V1
    - GITHUB_REPOS
    - googlelocal
    - music_brainz_20k
    - PANCANCER_ATLAS
    - PATENTS
    - stockindex
    - stockmarket
    - yelp
trials: 1
"""


def test_translator_fans_out_to_all_twelve_datasets(tmp_path):
    data_root = _make_fixture_root(tmp_path)
    spec = parse_spec_text(SPEC_TEMPLATE.format(data_root=data_root))
    cfg, trial_map = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    assert sorted(trial_map.keys()) == sorted([f"{slug}-q1" for slug in TWELVE])
    assert all(trial_map[f"{slug}-q1"] == (slug, 1) for slug in TWELVE)
    assert len(cfg.tasks) == 12


def test_translator_retry_zero_still_holds_at_twelve_datasets(tmp_path):
    """AC-4 from M2 must keep holding: max_retries=0 regardless of dataset count."""
    data_root = _make_fixture_root(tmp_path)
    spec = parse_spec_text(SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _ = spec_to_job_config(
        spec,
        job_name="x" * 16,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    assert cfg.retry.max_retries == 0
