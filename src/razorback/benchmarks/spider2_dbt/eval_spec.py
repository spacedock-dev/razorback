# ABOUTME: spider2-dbt gold eval-spec model + loader (one line of spider2_eval.jsonl).
# ABOUTME: Keeps spec-parsing separate from the duckdb_match comparison semantics.
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalSpec:
    """One Spider2-dbt gold eval entry (a line of spider2_eval.jsonl).

    condition_tabs: gold table names to compare.
    condition_cols: table name -> 0-based column indices (into SELECT *
        order) to restrict the comparison to. A table missing here means
        "compare all columns".
    ignore_orders: when True, compare row-multisets order-insensitively.
    """

    condition_tabs: list[str]
    condition_cols: dict[str, list[int]] = field(default_factory=dict)
    ignore_orders: bool = False


def load_eval_spec(path: Path) -> EvalSpec:
    """Load a single-task gold eval spec from a JSON object.

    Accepts either a bare JSON object or the first line of a
    spider2_eval.jsonl file (one task per line).
    """
    text = Path(path).read_text().strip()
    first_line = text.splitlines()[0] if text else "{}"
    raw = json.loads(first_line)
    return EvalSpec(
        condition_tabs=list(raw.get("condition_tabs", [])),
        condition_cols={
            k: list(v) for k, v in raw.get("condition_cols", {}).items()
        },
        ignore_orders=bool(raw.get("ignore_orders", False)),
    )
