# ABOUTME: PKG-13 T8 — hardened bookreview-q1 validator wrapping upstream.
# ABOUTME: Bounded-decade parse closes the substring leak observed in T14.

import importlib.util
import re
from pathlib import Path


# PKG-13: the upstream q1 validator accepts any string containing "2020" /
# "2020s", which lets an agent dump matching text from the SQL file and pass.
# The hardened check requires the answer to parse as a 4-digit year (with an
# optional trailing "s" for a decade) and equal the ground-truth decade
# exactly. The upstream substring check still runs first so a "wrong decade
# substring match" path stays rejected.
_GROUND_TRUTH_DECADE = "2020"

_DECADE_RE = re.compile(r"^\s*(\d{4})(s)?\s*$")


def _load_upstream():
    here = Path(__file__).parent
    upstream = here / "_upstream_validate.py"
    spec = importlib.util.spec_from_file_location("_upstream_validate", str(upstream))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def _matches_ground_truth_decade(answer: str) -> bool:
    match = _DECADE_RE.match(answer)
    if not match:
        return False
    year = match.group(1)
    return year == _GROUND_TRUTH_DECADE


def validate(answer):
    upstream_ok, reason = _load_upstream()(answer)
    if not upstream_ok:
        return (False, reason)
    if not isinstance(answer, str):
        return (False, "answer is not a string")
    if not _matches_ground_truth_decade(answer):
        return (
            False,
            "answer does not parse as the ground-truth decade (expected 4-digit year with optional trailing 's')",
        )
    return (True, "ok")
