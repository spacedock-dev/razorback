# ABOUTME: Batch-mode verifier — reads /work/answers.json, runs validate_qN.py per query.
# ABOUTME: Writes reward.json (mean reward) and reward_per_query.json (per-qN map).

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


_QN_RE = re.compile(r"^validate_q(\d+)\.py$")


def emit_reward(
    *, tests_dir: Path, answers_path: Path, reward_out: Path, per_query_out: Path
) -> None:
    answers = _read_answers(Path(answers_path))
    validators = _discover_validators(Path(tests_dir))
    per_query: dict[str, dict] = {}
    rewards: list[float] = []
    for query_id in sorted(validators.keys()):
        key = f"q{query_id}"
        answer = answers.get(key, "") if isinstance(answers, dict) else ""
        validate_fn = _load_validate(validators[query_id])
        if answer:
            is_valid, reason = validate_fn(answer)
        else:
            is_valid, reason = False, "empty answer"
        reward = 1.0 if is_valid else 0.0
        per_query[key] = {"reward": reward, "reason": reason}
        rewards.append(reward)
        if not is_valid:
            sys.stderr.write(f"DAB verify_batch ({key}): {reason}\n")
    mean_reward = (sum(rewards) / len(rewards)) if rewards else 0.0
    Path(reward_out).parent.mkdir(parents=True, exist_ok=True)
    Path(reward_out).write_text(json.dumps({"reward": mean_reward}) + "\n")
    Path(per_query_out).parent.mkdir(parents=True, exist_ok=True)
    Path(per_query_out).write_text(json.dumps(per_query, indent=2) + "\n")


def _read_answers(answers_path: Path) -> dict:
    if not answers_path.exists():
        return {}
    try:
        raw = json.loads(answers_path.read_text())
    except json.JSONDecodeError:
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _discover_validators(tests_dir: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for child in tests_dir.iterdir():
        m = _QN_RE.match(child.name)
        if m:
            out[int(m.group(1))] = child
    return out


def _load_validate(validate_py: Path):
    spec = importlib.util.spec_from_file_location(
        f"_dab_validate_{validate_py.stem}", str(validate_py)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-dir", required=True, type=Path)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--reward-out", required=True, type=Path)
    parser.add_argument("--per-query-out", required=True, type=Path)
    args = parser.parse_args()
    emit_reward(
        tests_dir=args.tests_dir,
        answers_path=args.answers,
        reward_out=args.reward_out,
        per_query_out=args.per_query_out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
