# ABOUTME: Verifier reward-emission shape — carry-forward from in-tree verify.py.
# ABOUTME: reward.json contains {"reward": 1.0} on valid answers, 0.0 otherwise.

import json
from pathlib import Path

from razorback_plugin_dab.verify.verify import emit_reward


def _write_validator(path: Path) -> None:
    path.write_text(
        "def validate(answer):\n"
        "    return (answer == 'right', '') if answer == 'right' else (False, 'wrong')\n"
    )


def test_valid_answer_writes_reward_1(tmp_path: Path):
    validator = tmp_path / "validate.py"
    _write_validator(validator)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "right"}))
    out = tmp_path / "reward.json"

    emit_reward(validate_py=validator, answers_path=answers, reward_out=out)

    payload = json.loads(out.read_text())
    assert payload == {"reward": 1.0}


def test_invalid_answer_writes_reward_0(tmp_path: Path):
    validator = tmp_path / "validate.py"
    _write_validator(validator)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "wrong"}))
    out = tmp_path / "reward.json"

    emit_reward(validate_py=validator, answers_path=answers, reward_out=out)

    payload = json.loads(out.read_text())
    assert payload == {"reward": 0.0}


def test_empty_answer_writes_reward_0(tmp_path: Path):
    validator = tmp_path / "validate.py"
    _write_validator(validator)
    answers = tmp_path / "answers.json"
    out = tmp_path / "reward.json"

    emit_reward(validate_py=validator, answers_path=answers, reward_out=out)

    payload = json.loads(out.read_text())
    assert payload == {"reward": 0.0}
