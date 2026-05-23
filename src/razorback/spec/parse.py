# ABOUTME: YAML → razorback Spec parser. Raises SpecError on invalid specs.
# ABOUTME: Wraps pydantic ValidationError into a typed razorback error.

from pathlib import Path

import yaml
from pydantic import ValidationError

from razorback.errors import SpecError
from razorback.spec.schema import Spec


_BENCHMARK_KIND_ALIASES = {
    # v2 spelling for the v1 in-tree DAB adapter. Both forms parse; the
    # internal model still uses kind="dab" so the existing translator path
    # is unchanged. AC-5: in-tree DAB is dev-only; canonical DAB is
    # kind: harbor_dab + dataset: dab@<version> (see entity
    # dab-harbor-dataset-definition).
    "in_tree_dab": "dab",
}


def parse_spec_text(text: str) -> Spec:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError(f"invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SpecError("spec must be a YAML mapping")
    bench = raw.get("benchmark")
    if isinstance(bench, dict):
        kind = bench.get("kind")
        if isinstance(kind, str) and kind in _BENCHMARK_KIND_ALIASES:
            bench["kind"] = _BENCHMARK_KIND_ALIASES[kind]
    try:
        return Spec.model_validate(raw)
    except ValidationError as exc:
        raise SpecError(str(exc)) from exc


def parse_spec_file(path: Path) -> Spec:
    return parse_spec_text(Path(path).read_text())
