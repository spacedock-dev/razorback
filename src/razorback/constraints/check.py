# ABOUTME: Compare a spec (or frozen spec) against a constraints file (§3.2).
# ABOUTME: Raises ConstraintViolation (exit 12) on pinned mismatch or undeclared mutation.

from typing import Any

from razorback.errors import ConstraintViolation


def check_spec_against_constraints(
    spec: dict,
    constraints: dict,
    *,
    baseline: dict | None = None,
) -> None:
    """Raise ConstraintViolation if any pinned field mismatches, or any baseline-vs-spec
    diverged field is not covered by mutation_surfaces.

    `spec` and `baseline` are parsed YAML dicts. Dotted-path keys in `pinned` and
    `mutation_surfaces` traverse the nested mapping.
    """
    pinned = constraints.get("pinned") or {}
    for path, expected in pinned.items():
        actual = _walk(spec, path)
        if actual != expected:
            raise ConstraintViolation(
                f"pinned field {path}: expected {expected!r}, got {actual!r}"
            )
    if baseline is not None:
        diverged = _diff_paths(baseline, spec)
        surfaces = constraints.get("mutation_surfaces") or []
        for path in diverged:
            if not any(path == s or path.startswith(s + ".") for s in surfaces):
                raise ConstraintViolation(
                    f"diverged field {path} is not under any declared "
                    f"mutation_surfaces {surfaces!r}"
                )


def _walk(d: Any, dotted: str) -> Any:
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _diff_paths(a: Any, b: Any, prefix: str = "") -> list[str]:
    out: list[str] = []
    if not isinstance(a, dict) or not isinstance(b, dict):
        if a != b:
            out.append(prefix)
        return out
    for k in set(a) | set(b):
        path = f"{prefix}.{k}" if prefix else k
        av = a.get(k)
        bv = b.get(k)
        if isinstance(av, dict) and isinstance(bv, dict):
            out.extend(_diff_paths(av, bv, prefix=path))
        elif av != bv:
            out.append(path)
    return out
