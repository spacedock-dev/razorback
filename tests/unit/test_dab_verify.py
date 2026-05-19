# ABOUTME: Unit tests for the DAB verify module (§6.5, AC-3).
# ABOUTME: Reads answers.json, imports per-query validate.py, writes /logs/verifier/reward.json.

import json
from pathlib import Path

from razorback.benchmarks.dab.verify import emit_reward


def _validate_py(root: Path) -> Path:
    p = root / "validate.py"
    p.write_text(
        "def validate(s):\n"
        "    return ('2020' in s, 'present' if '2020' in s else 'missing')\n"
    )
    return p


def test_emit_reward_writes_1_0_on_pass(tmp_path):
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "the answer is the 2020s decade"}))
    reward_out = tmp_path / "reward.json"
    emit_reward(validate_py=_validate_py(tmp_path), answers_path=answers, reward_out=reward_out)
    assert json.loads(reward_out.read_text()) == {"reward": 1.0}


def test_emit_reward_writes_0_0_on_fail(tmp_path):
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "wrong"}))
    reward_out = tmp_path / "reward.json"
    emit_reward(validate_py=_validate_py(tmp_path), answers_path=answers, reward_out=reward_out)
    payload = json.loads(reward_out.read_text())
    assert payload["reward"] == 0.0
    # Reason stays out of rewards (harbor's VerifierResult.rewards is dict[str, number]).
    assert all(isinstance(v, (int, float)) for v in payload.values())


def test_emit_reward_treats_missing_answers_as_empty(tmp_path):
    reward_out = tmp_path / "reward.json"
    emit_reward(
        validate_py=_validate_py(tmp_path),
        answers_path=tmp_path / "nope.json",
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text())["reward"] == 0.0


def test_emit_reward_treats_malformed_answers_as_empty(tmp_path):
    answers = tmp_path / "answers.json"
    answers.write_text("not json")
    reward_out = tmp_path / "reward.json"
    emit_reward(validate_py=_validate_py(tmp_path), answers_path=answers, reward_out=reward_out)
    assert json.loads(reward_out.read_text())["reward"] == 0.0
