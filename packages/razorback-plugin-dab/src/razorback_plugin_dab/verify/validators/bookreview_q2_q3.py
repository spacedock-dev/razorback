# ABOUTME: PKG-13 T9 — hardened bookreview-q2/q3 validator wrapping upstream.
# ABOUTME: Length cap closes the "agent dumped the SQL file" substring leak.

import importlib.util
from pathlib import Path


# PKG-13: q2/q3 pass when every ground-truth book title appears as a substring
# of the answer. Today an agent that dumps the entire books_info.sql file
# satisfies that, because every title is in the dump. The cap is generous
# enough that a comma-separated short answer always fits, and tight enough
# that pasting the SQL dump cannot pass. The cap was chosen by measuring
# canonical answers (~250-400 chars), then 4x for slack, rounded to 2000.
_ANSWER_MAX_LEN = 2000


def _load_upstream():
    here = Path(__file__).parent
    upstream = here / "_upstream_validate.py"
    spec = importlib.util.spec_from_file_location("_upstream_validate", str(upstream))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def validate(answer):
    if not isinstance(answer, str):
        return (False, "answer is not a string")
    if len(answer) > _ANSWER_MAX_LEN:
        return (False, f"answer too long ({len(answer)} > {_ANSWER_MAX_LEN} chars)")
    return _load_upstream()(answer)
