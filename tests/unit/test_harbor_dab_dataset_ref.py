# ABOUTME: AC-2 — HarborDabBenchmarkBlock accepts dataset: <name>@<version> in place of data_root+datasets.
# ABOUTME: Old-shape specs still parse (compat). Mixed shapes raise.

from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text
from razorback.spec.schema import HarborDabBenchmarkBlock


def _spec(benchmark_yaml: str) -> str:
    return (
        "version: 1\n"
        "experiment: ac2-test\n"
        "agent:\n"
        "  kind: nop\n"
        f"benchmark:\n{benchmark_yaml}\n"
        "trials: 1\n"
    )


def test_harbor_dab_accepts_dataset_ref_without_data_root() -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  workspace_variant: spacedock\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset == "dab@1.0"
    assert spec.benchmark.datasets == []
    assert spec.benchmark.data_root is None


def test_harbor_dab_dataset_ref_with_subset() -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  datasets: [bookreview, agnews]\n"
        "  workspace_variant: spacedock\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset == "dab@1.0"
    assert spec.benchmark.datasets == ["bookreview", "agnews"]


def test_harbor_dab_legacy_shape_still_parses(tmp_path: Path) -> None:
    """AC-2 compat: old harbor_dab specs (no `dataset:`) keep working."""
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset is None
    assert spec.benchmark.data_root == tmp_path


def test_harbor_dab_legacy_shape_requires_data_root_when_no_dataset_ref(
    tmp_path: Path,
) -> None:
    with pytest.raises(SpecError, match="(?i)data_root.*required"):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            "  datasets: [bookreview]\n"
        ))


def test_harbor_dab_rejects_unknown_dataset_ref_format() -> None:
    with pytest.raises(SpecError, match="(?i)dataset.*format"):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            "  dataset: dab-no-version\n"
        ))


def test_translator_uses_dataset_ref_to_enumerate_datasets(
    tmp_path: Path, monkeypatch
) -> None:
    """When `dataset:` is set and `datasets:` is empty, the translator
    enumerates ALL datasets from the definition. Mock the plugin subprocess so
    we just observe the dataset list that was passed."""
    from razorback.translate import spec_to_job_config

    captured_datasets: list[str] = []

    def fake_run(cmd, capture_output, text):
        for i, arg in enumerate(cmd):
            if arg == "--datasets":
                captured_datasets.append(cmd[i + 1])
        out_idx = cmd.index("--out") + 1
        out_dir = Path(cmd[out_idx])
        out_dir.mkdir(parents=True, exist_ok=True)
        task_dir = out_dir / captured_datasets[-1]
        task_dir.mkdir(exist_ok=True)

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("DATAAGENTBENCH_DATA_ROOT", str(tmp_path / "fake-data"))

    spec = parse_spec_text(
        "version: 1\n"
        "experiment: ac2-translator\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n"
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  workspace_variant: spacedock\n"
        "  query_mode: batch\n"
        "trials: 1\n"
    )
    jobs_dir = tmp_path / "jobs"
    spec_to_job_config(
        spec, job_name="j", jobs_dir=jobs_dir, tasks_root=tmp_path / "tr"
    )
    assert sorted(captured_datasets) == sorted([
        "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1",
        "GITHUB_REPOS", "googlelocal", "music_brainz_20k",
        "PANCANCER_ATLAS", "PATENTS", "stockindex", "stockmarket", "yelp",
    ])


def test_translator_legacy_shape_still_works(tmp_path: Path, monkeypatch) -> None:
    """AC-2 compat: old harbor_dab specs (no `dataset:`) still route through
    the translator without consulting the dataset definition."""
    from razorback.translate import spec_to_job_config

    seen_data_root: list[str] = []

    def fake_run(cmd, capture_output, text):
        for i, arg in enumerate(cmd):
            if arg == "--data-root":
                seen_data_root.append(cmd[i + 1])
        out_idx = cmd.index("--out") + 1
        out_dir = Path(cmd[out_idx])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "bookreview").mkdir(exist_ok=True)

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)

    fake_data = tmp_path / "fake-data"
    fake_data.mkdir()
    spec = parse_spec_text(
        "version: 1\n"
        "experiment: ac2-legacy\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n"
        "  kind: harbor_dab\n"
        f"  data_root: {fake_data}\n"
        "  datasets: [bookreview]\n"
        "  query_mode: batch\n"
        "trials: 1\n"
    )
    spec_to_job_config(
        spec, job_name="j", jobs_dir=tmp_path / "jobs", tasks_root=tmp_path / "tr",
    )
    assert seen_data_root == [str(fake_data.resolve())]
