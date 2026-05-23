# ABOUTME: rk score loader — walks run-dir for per-trial state + stratum tag.
# ABOUTME: TrialRecord is the contract every downstream score module consumes.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from razorback.errors import ConfigInvalidError


class ScoreInputError(ConfigInvalidError):
    """Run-dir is missing required input (result.json or stratum tag)."""


@dataclass(frozen=True)
class TrialRecord:
    trial_name: str
    stratum: str
    state: str
    passed: bool | None
    reward: float | None
    error_class: str | None
    stratum_payload: dict[str, Any] | None = None


_NON_TRIAL_NAMES = {
    "summary.json",
    "per_trial_outcomes.json",
    "provenance.yaml",
    "spec.frozen.yaml",
    "result.json",
    "config.json",
    "job.log",
    "lock.json",
    "manifest.json",
    "events.jsonl",
    "tasks",
    "_razorback",
}


def load_run_dir(run_dir: Path) -> list[TrialRecord]:
    """Walk <run-dir>/<trial-name>/, read result.json + agent/stratum.json per trial."""
    run_dir = Path(run_dir)
    if not run_dir.exists():
        raise ScoreInputError(f"run-dir does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise ScoreInputError(f"run-dir is not a directory: {run_dir}")

    records: list[TrialRecord] = []
    for child in sorted(run_dir.iterdir()):
        if not child.is_dir() or child.name in _NON_TRIAL_NAMES:
            continue
        result_path = child / "result.json"
        if not result_path.exists():
            continue
        records.append(_read_trial(child))
    return records


def _read_trial(trial_dir: Path) -> TrialRecord:
    result = _read_json(trial_dir / "result.json")
    stratum_payload = _resolve_stratum_payload(trial_dir)
    stratum = _stratum_label(trial_dir, stratum_payload)
    exception_info = result.get("exception_info")
    verifier_result = result.get("verifier_result")

    if exception_info is not None:
        return TrialRecord(
            trial_name=trial_dir.name,
            stratum=stratum,
            state="errored",
            passed=None,
            reward=None,
            error_class=exception_info.get("exception_type"),
            stratum_payload=stratum_payload,
        )

    if verifier_result is None:
        return TrialRecord(
            trial_name=trial_dir.name,
            stratum=stratum,
            state="errored",
            passed=None,
            reward=None,
            error_class="MissingVerifierResult",
            stratum_payload=stratum_payload,
        )

    reward = _extract_reward(verifier_result)
    return TrialRecord(
        trial_name=trial_dir.name,
        stratum=stratum,
        state="completed",
        passed=(reward is not None and reward >= 1.0),
        reward=reward,
        error_class=None,
        stratum_payload=stratum_payload,
    )


def _extract_reward(verifier_result: dict[str, Any]) -> float | None:
    rewards = verifier_result.get("rewards") or {}
    if "reward" in rewards:
        return float(rewards["reward"])
    if rewards:
        first = next(iter(rewards.values()))
        return float(first)
    return None


def _resolve_stratum_payload(trial_dir: Path) -> dict[str, Any]:
    """Read stratum from sidecars or PKG-40 task-view manifests."""
    candidates = [
        trial_dir / "agent" / "stratum.json",
        trial_dir / "logs" / "verifier" / "stratum.json",
    ]
    # Harbor v2 task layout writes verifier sidecars under
    # steps/<step-name>/verifier/. Discover stratum.json in any of those.
    steps_root = trial_dir / "steps"
    if steps_root.is_dir():
        for step_dir in sorted(steps_root.iterdir()):
            candidates.append(step_dir / "verifier" / "stratum.json")
    stratum_payload: dict[str, Any] | None = None
    for candidate in candidates:
        if candidate.exists():
            stratum_payload = _read_json(candidate).get("stratum")
            break

    if stratum_payload is None:
        stratum_payload = _resolve_stratum_from_task_view_manifest(trial_dir)
    if stratum_payload is None:
        raise ScoreInputError(
            f"trial {trial_dir.name} has no stratum tag "
            "(expected agent/stratum.json or _razorback/task_views/*/view_manifest.json)"
        )
    return stratum_payload


def _stratum_label(trial_dir: Path, stratum_payload: dict[str, Any]) -> str:
    if "dataset" in stratum_payload and _is_scalar(stratum_payload["dataset"]):
        return str(stratum_payload["dataset"])

    for value in stratum_payload.values():
        if _is_scalar(value):
            return str(value)

    raise ScoreInputError(
        f"trial {trial_dir.name} stratum has no scalar field to use as label"
    )


def _resolve_stratum_from_task_view_manifest(trial_dir: Path) -> dict[str, Any] | None:
    views_root = trial_dir.parent / "_razorback" / "task_views"
    if not views_root.is_dir():
        return None

    trial_prefix = trial_dir.name.split("__", 1)[0]
    for manifest_path in sorted(views_root.glob("*/view_manifest.json")):
        view_prefix = manifest_path.parent.name[:32].rstrip("_-")
        if trial_prefix != view_prefix:
            continue
        payload = _read_json(manifest_path)
        benchmark_kind = payload.get("benchmark_kind")
        benchmark_task_id = payload.get("benchmark_task_id")
        if not benchmark_kind or not benchmark_task_id:
            return None
        return {
            "dataset": str(benchmark_kind),
            "query_id": str(benchmark_task_id),
            "benchmark_kind": str(benchmark_kind),
            "benchmark_task_id": str(benchmark_task_id),
        }
    return None


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and not isinstance(value, list) and not isinstance(value, dict)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
