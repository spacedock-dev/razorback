# ABOUTME: spider2-dbt verify.py CLI + materializer-emission tests (AC-3).
# ABOUTME: emit_reward writes harbor-shaped reward.json; the view carries verifier assets.
import json
from pathlib import Path

import duckdb

from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)
from razorback.benchmarks.spider2_dbt.verify import emit_reward

_SOURCE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "spider2_dbt"
    / "harbor_task_minimal"
    / "spider2-fixture-001"
)


def _build_db(path, rows):
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE orders (a INTEGER)")
        con.executemany("INSERT INTO orders VALUES (?)", [(r,) for r in rows])
    finally:
        con.close()


def _spec(path):
    # Real Spider2 gold-line shape: evaluation.parameters with per-table lists.
    path.write_text(
        json.dumps(
            {
                "instance_id": "cli-001",
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {
                        "gold": "gold.duckdb",
                        "condition_tabs": ["orders"],
                        "condition_cols": [[]],
                        "ignore_orders": [True],
                    },
                },
            }
        )
        + "\n"
    )
    return path


def test_spider2_dbt_verify_cli_emits_reward_one_on_match(tmp_path):
    _build_db(tmp_path / "pred.duckdb", [1, 2])
    _build_db(tmp_path / "gold.duckdb", [2, 1])
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=_spec(tmp_path / "spider2_eval.jsonl"),
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text()) == {"reward": 1.0}


def test_spider2_dbt_verify_cli_emits_reward_zero_on_mismatch(tmp_path):
    _build_db(tmp_path / "pred.duckdb", [1, 2])
    _build_db(tmp_path / "gold.duckdb", [9, 9])
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=_spec(tmp_path / "spider2_eval.jsonl"),
        reward_out=reward_out,
    )
    payload = json.loads(reward_out.read_text())
    assert payload == {"reward": 0.0}
    # parent dir was created by emit_reward (mirrors dab/verify.py:31)
    assert reward_out.parent.is_dir()


def test_spider2_dbt_verify_cli_missing_predicted_scores_zero(tmp_path):
    # A predicted DB the agent never produced is a 0.0 reward, not a crash.
    _build_db(tmp_path / "gold.duckdb", [1])
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "does-not-exist.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=_spec(tmp_path / "spider2_eval.jsonl"),
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text()) == {"reward": 0.0}


def test_spider2_dbt_verify_cli_empty_spec_scores_zero_not_one(tmp_path):
    # FAIL-CLOSED (cycle-2 B1): a real predicted DB matching a gold DB, but with
    # an empty / malformed gold spec, must score 0.0 — never silently 1.0. An
    # empty condition_tabs is the hazard (compare_duckdb's AND-loop returns True
    # on zero tables), so emit_reward must surface it as a NON-match.
    _build_db(tmp_path / "pred.duckdb", [1, 2])
    _build_db(tmp_path / "gold.duckdb", [1, 2])  # identical -> would be 1.0 if scored
    empty_spec = tmp_path / "spider2_eval.jsonl"
    empty_spec.write_text("")
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=empty_spec,
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text()) == {"reward": 0.0}


def test_spider2_dbt_verify_cli_wrong_func_scores_zero_not_one(tmp_path):
    # A schema-drifted spec (non-duckdb_match func) over a matching DB pair must
    # also fail closed to 0.0, not crash and not pass.
    _build_db(tmp_path / "pred.duckdb", [1, 2])
    _build_db(tmp_path / "gold.duckdb", [1, 2])
    bad_spec = tmp_path / "spider2_eval.jsonl"
    bad_spec.write_text(
        json.dumps(
            {
                "instance_id": "x",
                "evaluation": {
                    "func": "string_match",
                    "parameters": {"gold": "gold.duckdb", "condition_tabs": ["orders"]},
                },
            }
        )
        + "\n"
    )
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=bad_spec,
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text()) == {"reward": 0.0}


def test_spider2_dbt_verify_view_carries_verifier_assets(tmp_path):
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )
    tests = view / "tests"
    # comparator + cli + spec modules and gold data are present for the verifier
    for name in (
        "duckdb_match.py",
        "eval_spec.py",
        "verify.py",
        "gold.duckdb",
        "spider2_eval.jsonl",
        "test.sh",
    ):
        assert (tests / name).is_file(), f"missing verifier asset: {name}"
    # test.sh is executable
    assert (tests / "test.sh").stat().st_mode & 0o111
    # leakage-clean: no `gold/` path segment survived in the agent-facing view
    assert not (view / "tests" / "gold").exists()
    assert not list(view.rglob("gold/*"))


def _write_gold_source(
    source: Path, *, gold_basename: str, with_default_gold: bool
) -> Path:
    # A minimal spider2-dbt source task whose gold line names a NON-default gold
    # DB (e.g. playbook.duckdb), with NO gold.duckdb present. Mirrors a real
    # Spider2 task that names its gold per task.
    (source / "environment").mkdir(parents=True)
    (source / "dbt_project" / "models").mkdir(parents=True)
    (source / "task.toml").write_text(
        "\n".join(
            [
                'schema_version = "1.0"',
                "[environment]",
                'os = "linux"',
                "cpus = 1",
                "memory_mb = 1024",
                "storage_mb = 1024",
                "",
            ]
        )
    )
    (source / "instruction.md").write_text("Fix the dbt project.\n")
    (source / "dbt_project" / "dbt_project.yml").write_text(
        "name: example\nprofile: example\n"
    )
    (source / "dbt_project" / "models" / "example.sql").write_text("select 1\n")
    (source / "environment" / "Dockerfile").write_text(
        "FROM python:3.12\nWORKDIR /app\nCMD [\"bash\"]\n"
    )
    gold_dir = source / "tests" / "gold"
    gold_dir.mkdir(parents=True)
    # The NAMED gold DB (the one the spec points at).
    _build_db(gold_dir / gold_basename, [1, 2])
    if with_default_gold:
        _build_db(gold_dir / "gold.duckdb", [9, 9])  # a decoy default
    (gold_dir / "spider2_eval.jsonl").write_text(
        json.dumps(
            {
                "instance_id": "playbook001",
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {
                        "gold": gold_basename,
                        "condition_tabs": ["orders"],
                        "condition_cols": [[]],
                        "ignore_orders": [True],
                    },
                },
            }
        )
        + "\n"
    )
    return source


def test_spider2_dbt_verify_view_uses_non_default_gold_basename(tmp_path):
    # REGRESSION (cycle-3): the gold DB basename is driven by parameters.gold,
    # NOT hardcoded gold.duckdb. A task naming playbook.duckdb (and shipping NO
    # gold.duckdb) must copy playbook.duckdb into the verifier-only tests/ and
    # emit --gold-db /tests/playbook.duckdb.
    source = _write_gold_source(
        tmp_path / "source", gold_basename="playbook.duckdb", with_default_gold=False
    )
    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="playbook001",
    )
    tests = view / "tests"
    # The NAMED gold file is copied; the hardcoded gold.duckdb is NOT invented.
    assert (tests / "playbook.duckdb").is_file()
    assert not (tests / "gold.duckdb").exists()
    # test.sh scores against the named file.
    test_sh = (tests / "test.sh").read_text()
    assert "--gold-db /tests/playbook.duckdb" in test_sh
    assert "/tests/gold.duckdb" not in test_sh
    # leakage-clean: no gold/ segment survives.
    assert not (view / "tests" / "gold").exists()
    assert not list(view.rglob("gold/*"))


def test_spider2_dbt_verify_view_named_gold_actually_scores(tmp_path):
    # End-to-end: a predicted DB matching the NAMED gold scores 1.0 through the
    # emitted verifier, proving the named file (not a missing/decoy gold.duckdb)
    # is the one actually scored.
    source = _write_gold_source(
        tmp_path / "source", gold_basename="playbook.duckdb", with_default_gold=False
    )
    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="playbook001",
    )
    tests = view / "tests"
    predicted = tmp_path / "pred.duckdb"
    _build_db(predicted, [2, 1])  # reordered; ignore_orders -> match
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=predicted,
        gold_db=tests / "playbook.duckdb",
        eval_spec=tests / "spider2_eval.jsonl",
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text()) == {"reward": 1.0}


def test_spider2_dbt_verify_view_missing_named_gold_fails_closed(tmp_path):
    # Fail closed: if the spec names a gold DB that does NOT exist under
    # tests/gold/, materialization must raise rather than silently emit a
    # verifier that scores against a missing file.
    source = _write_gold_source(
        tmp_path / "source", gold_basename="playbook.duckdb", with_default_gold=False
    )
    # Delete the named gold so the spec points at a missing file.
    (source / "tests" / "gold" / "playbook.duckdb").unlink()
    import pytest

    with pytest.raises((FileNotFoundError, ValueError)):
        materialize_spider2_harbor_task_view(
            source_task_dir=source,
            view_root=tmp_path / "views",
            task_slug="playbook001",
        )


def test_spider2_dbt_verify_view_missing_gold_dir_fails_closed(tmp_path):
    # Every spider2-dbt task is duckdb_match-scored, so a source with NO
    # tests/gold/spider2_eval.jsonl must be a hard materialization error — NOT a
    # silent pass-through that leaves the source test.sh (e.g. a stub `exit 0`)
    # in place and yields an unscored / trivially-passing task.
    import shutil as _shutil

    import pytest

    source = _write_gold_source(
        tmp_path / "source", gold_basename="g.duckdb", with_default_gold=False
    )
    _shutil.rmtree(source / "tests" / "gold")
    with pytest.raises(FileNotFoundError):
        materialize_spider2_harbor_task_view(
            source_task_dir=source,
            view_root=tmp_path / "views",
            task_slug="playbook001",
        )


def test_spider2_dbt_verify_test_sh_uses_resolved_db_name(tmp_path):
    # RIDER: the emitted test.sh predicted-DB path must come from
    # resolve_spider2_db_name, NOT a hardcoded /app/spider2.duckdb. This
    # fixture ships no profiles.yml / *.duckdb, so the resolver falls back to
    # the task slug -> the predicted path is /app/<slug>.duckdb (a NON-spider2
    # db name), proving the resolver is consumed.
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE,
        view_root=tmp_path / "views",
        task_slug="not-spider2-slug",
    )
    test_sh = (view / "tests" / "test.sh").read_text()
    assert "/app/not-spider2-slug.duckdb" in test_sh
    assert "/app/spider2.duckdb" not in test_sh


def test_spider2_dbt_verify_test_sh_quotes_predicted_db_against_injection(tmp_path):
    # SECURITY (cycle-5 symmetric): db_name is resolved from the task's
    # profiles.yml `path:` (external input). A path carrying shell metacharacters
    # must NOT be emitted raw into the verifier test.sh --predicted-db arg, or it
    # executes during verification. shlex.quote at the emission point neutralizes
    # it (the same class the gold allowlist blocks for --gold-db).
    import shlex

    source = _write_gold_source(
        tmp_path / "source", gold_basename="g.duckdb", with_default_gold=False
    )
    (source / "dbt_project" / "profiles.yml").write_text(
        "\n".join(
            [
                "example:",
                "  outputs:",
                "    dev:",
                "      type: duckdb",
                "      path: evil$(touch pwned).duckdb",
                "  target: dev",
                "",
            ]
        )
    )
    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="playbook001",
    )
    test_sh = (view / "tests" / "test.sh").read_text()
    # The metacharacter path is present only in its safely-quoted form.
    assert shlex.quote("/app/evil$(touch pwned).duckdb") in test_sh
    assert "--predicted-db /app/evil$(touch pwned).duckdb" not in test_sh
