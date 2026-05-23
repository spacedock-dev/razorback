# ABOUTME: YAML → razorback Spec parser. Raises SpecError on invalid specs.
# ABOUTME: Wraps pydantic ValidationError into a typed razorback error.

from pathlib import Path

import yaml
from pydantic import ValidationError

from razorback.errors import SpecError
from razorback.spec.schema import Spec


def parse_spec_text(text: str) -> Spec:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError(f"invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SpecError("spec must be a YAML mapping")
    try:
        return Spec.model_validate(raw)
    except ValidationError as exc:
        raise SpecError(str(exc)) from exc


def parse_spec_file(path: Path) -> Spec:
    return parse_spec_text(Path(path).read_text())
