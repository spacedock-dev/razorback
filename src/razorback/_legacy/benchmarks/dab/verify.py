# ABOUTME: DAB verifier — reads /work/answers.json, calls a per-query validate.py, writes reward.json.
# ABOUTME: §6.5 — emits harbor's per-task reward shape (dict at /logs/verifier/reward.json).

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def emit_reward(
    *,
    validate_py: Path,
    answers_path: Path,
    reward_out: Path,
) -> None:
    """Compute and write the harbor-shaped reward file.

    `validate_py` points at the dataset's per-query validate.py. The DAB datasets ship
    validate.py with the ground truth inlined; ground_truth.csv is not read by the
    validator at runtime, only by the failure-reason rendering.
    """
    llm_answer = _read_answer(Path(answers_path))
    validate_fn = _load_validate(Path(validate_py))

    if llm_answer:
        is_valid, reason = validate_fn(llm_answer)
    else:
        is_valid, reason = False, "empty answer"
    payload = {"reward": 1.0 if is_valid else 0.0}
    Path(reward_out).parent.mkdir(parents=True, exist_ok=True)
    Path(reward_out).write_text(json.dumps(payload) + "\n")
    if not is_valid:
        sys.stderr.write(f"DAB verify ({validate_py}): {reason}\n")


def _read_answer(answers_path: Path) -> str:
    if not answers_path.exists():
        return ""
    try:
        raw = json.loads(answers_path.read_text())
    except json.JSONDecodeError:
        return ""
    if isinstance(raw, dict) and "answer" in raw:
        return str(raw["answer"])
    if isinstance(raw, str):
        return raw
    return ""


def _load_validate(validate_py: Path):
    if not validate_py.exists():
        raise FileNotFoundError(f"validate.py not found: {validate_py}")
    spec = importlib.util.spec_from_file_location("_dab_validate", str(validate_py))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-py", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--reward-out", type=Path, required=True)
    args = parser.parse_args()
    emit_reward(
        validate_py=args.validate_py,
        answers_path=args.answers,
        reward_out=args.reward_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
