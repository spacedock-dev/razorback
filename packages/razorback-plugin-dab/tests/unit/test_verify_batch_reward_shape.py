# ABOUTME: Batch verifier reward-emission shape for generated DAB task validators.
# ABOUTME: Keeps verifier dependency failures loud instead of scoring them as wrong answers.

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks
from razorback_plugin_dab.verify import verify_batch as verify_batch_module


def _build_common_scaffold_data_root(root: Path) -> Path:
    data_root = root / "data"
    scaffold_validate = data_root / "common_scaffold" / "validate"
    scaffold_validate.mkdir(parents=True)
    (data_root / "common_scaffold" / "__init__.py").write_text("")
    (scaffold_validate / "__init__.py").write_text("")
    (scaffold_validate / "levenshtein.py").write_text(
        "def levenshtein(left, right):\n"
        "    return 0 if left == right else 1\n"
    )

    qdir = data_root / "query_PATENTS"
    qdir.mkdir(parents=True)
    (qdir / "db_description.txt").write_text("Synthetic affected DAB dataset.")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text(json.dumps({"question": "Return abc."}))
    (q1 / "validate.py").write_text(
        "from common_scaffold.validate.levenshtein import levenshtein\n\n"
        "def validate(answer):\n"
        "    distance = levenshtein(answer, 'abc')\n"
        "    return (distance == 0, f'distance={distance}')\n"
    )
    return data_root


def _run_generated_verify_batch(
    *, tests_dir: Path, answers_path: Path, reward_out: Path, per_query_out: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(tests_dir / "verify_batch.py"),
            "--tests-dir",
            str(tests_dir),
            "--answers",
            str(answers_path),
            "--reward-out",
            str(reward_out),
            "--per-query-out",
            str(per_query_out),
        ],
        capture_output=True,
        text=True,
    )


def test_batch_verify_writes_artifacts_when_validator_imports_common_scaffold(
    tmp_path: Path,
) -> None:
    data_root = _build_common_scaffold_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="PATENTS",
        tasks_root=tmp_path / "tasks",
        query_mode="batch",
    )
    tests_dir = manifest[0]["task_dir"] / "tests"
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"q1": "abc"}))
    reward_out = tmp_path / "reward.json"
    per_query_out = tmp_path / "reward_per_query.json"

    result = _run_generated_verify_batch(
        tests_dir=tests_dir,
        answers_path=answers,
        reward_out=reward_out,
        per_query_out=per_query_out,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(reward_out.read_text()) == {"reward": 1.0}
    assert json.loads(per_query_out.read_text())["q1"]["reward"] == 1.0


def test_batch_verify_does_not_mask_validator_import_errors(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    shutil.copy2(Path(verify_batch_module.__file__), tests_dir / "verify_batch.py")
    (tests_dir / "validate_q1.py").write_text(
        "import missing_verifier_dependency\n\n"
        "def validate(answer):\n"
        "    return (True, 'ok')\n"
    )
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"q1": "anything"}))
    reward_out = tmp_path / "reward.json"
    per_query_out = tmp_path / "reward_per_query.json"

    result = _run_generated_verify_batch(
        tests_dir=tests_dir,
        answers_path=answers,
        reward_out=reward_out,
        per_query_out=per_query_out,
    )

    assert result.returncode != 0
    assert "ModuleNotFoundError" in result.stderr
    assert "missing_verifier_dependency" in result.stderr
    assert not reward_out.exists()
    assert not per_query_out.exists()


def test_batch_verify_isolates_per_query_runtime_validator_error(tmp_path: Path) -> None:
    """A single query's validator raising at call time (e.g. a non-string answer)
    must score that query 0 and continue grading the rest — not abort the whole
    dataset (which would drop it from the run as a RewardFileNotFoundError)."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    shutil.copy2(Path(verify_batch_module.__file__), tests_dir / "verify_batch.py")
    # q1 validator crashes on a non-string answer; q2 validator is well-behaved.
    (tests_dir / "validate_q1.py").write_text(
        "def validate(answer):\n"
        "    return (answer.lower() == 'x', 'checked')\n"
    )
    (tests_dir / "validate_q2.py").write_text(
        "def validate(answer):\n"
        "    return (answer == 'ok', 'checked')\n"
    )
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"q1": ["a", "b"], "q2": "ok"}))  # q1 is a LIST
    reward_out = tmp_path / "reward.json"
    per_query_out = tmp_path / "reward_per_query.json"

    result = _run_generated_verify_batch(
        tests_dir=tests_dir,
        answers_path=answers,
        reward_out=reward_out,
        per_query_out=per_query_out,
    )

    assert result.returncode == 0, result.stderr
    per_query = json.loads(per_query_out.read_text())
    assert per_query["q1"]["reward"] == 0.0
    assert "validator error" in per_query["q1"]["reason"]
    assert per_query["q2"]["reward"] == 1.0  # the good query still graded
    assert json.loads(reward_out.read_text()) == {"reward": 0.5}
