# ABOUTME: spider2-dbt gold eval-spec model + loader (one line of spider2_eval.jsonl).
# ABOUTME: Mirrors Spider2 evaluate.py: evaluation.parameters drives duckdb_match.
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalSpec:
    """One Spider2-dbt gold eval entry (a line of spider2_eval.jsonl).

    Mirrors the real Spider2 gold-line shape consumed by
    ``spider2-dbt/evaluation_suite/evaluate.py``::

        {"instance_id": "...",
         "evaluation": {"func": "duckdb_match",
                        "parameters": {"gold": "<gold.duckdb basename>",
                                       "condition_tabs": ["t1", "t2"],
                                       "condition_cols": [[0, 2], []],
                                       "ignore_orders": [true, false]}}}

    The three list fields are positional and parallel to ``condition_tabs``:

    condition_tabs: gold/pred table names to compare (``List[str]``).
    condition_cols: per-table 0-based gold column indices to restrict the
        gold side to before column-containment (``List[List[int]]``). An
        empty inner list means "use all gold columns" for that table. This
        mirrors Spider2 ``duckdb_match``'s ``condition_cols[i]`` argument to
        ``compare_pandas_table``.
    ignore_orders: per-table flag for order-insensitive per-column compare
        (``List[bool]``).

    Per Spider2 ``duckdb_match`` defaults: a missing/empty ``condition_cols``
    becomes ``[[]] * len(condition_tabs)`` and a missing ``ignore_orders``
    becomes ``[False] * len(condition_tabs)``.
    """

    condition_tabs: list[str]
    condition_cols: list[list[int]] = field(default_factory=list)
    ignore_orders: list[bool] = field(default_factory=list)

    def __post_init__(self) -> None:
        n = len(self.condition_tabs)
        # Fail closed: a zero-table spec would make compare_duckdb's AND-loop
        # never run and return True — silently scoring every prediction 1.0.
        # A corrupted/truncated/schema-drifted gold line must NOT score as a
        # match, so refuse to construct an empty-condition_tabs spec.
        if n == 0:
            raise ValueError(
                "EvalSpec requires a non-empty condition_tabs; a zero-table "
                "spec would score every prediction as a match (fail-open)"
            )
        # Normalize to Spider2 duckdb_match defaults so the comparator can
        # index condition_cols[i] / ignore_orders[i] for every table.
        cols = self.condition_cols
        if not cols or cols in ([[]], [None]):
            object.__setattr__(self, "condition_cols", [[] for _ in range(n)])
        orders = self.ignore_orders
        if not orders:
            object.__setattr__(self, "ignore_orders", [False] * n)
        if len(self.condition_cols) != n:
            raise ValueError(
                f"condition_cols ({len(self.condition_cols)}) must be parallel "
                f"to condition_tabs ({n})"
            )
        if len(self.ignore_orders) != n:
            raise ValueError(
                f"ignore_orders ({len(self.ignore_orders)}) must be parallel "
                f"to condition_tabs ({n})"
            )


def load_eval_spec(path: Path) -> EvalSpec:
    """Load a single-task gold eval spec from a spider2_eval.jsonl line.

    Reads the first line (one task per line), drills into
    ``evaluation.parameters`` (the shape Spider2 ``evaluate.py`` passes to
    ``duckdb_match``), and returns an :class:`EvalSpec`. Tolerates a bare
    ``parameters``-shaped object (no ``evaluation`` wrapper) for fixtures.

    Fails closed on a corrupted/truncated/schema-drifted gold line: an empty
    file, a wrong ``evaluation.func``, or a missing/empty ``condition_tabs``
    each raise ``ValueError`` rather than yielding a zero-table spec that
    ``compare_duckdb`` would silently score as a match (reward 1.0).
    """
    text = Path(path).read_text().strip()
    if not text:
        raise ValueError(
            f"empty gold eval spec at {path}: cannot score a missing/truncated "
            "spider2_eval.jsonl (fail-open guard)"
        )
    first_line = text.splitlines()[0]
    raw = json.loads(first_line)

    # When the real Spider2 evaluation wrapper is present, the func MUST be
    # duckdb_match — any other func means this verifier cannot faithfully score
    # the line, so refuse rather than fall through to a match.
    evaluation = raw.get("evaluation")
    if evaluation is not None:
        func = evaluation.get("func")
        if func != "duckdb_match":
            raise ValueError(
                f"unsupported evaluation.func {func!r} in {path}: this verifier "
                "only scores 'duckdb_match' (fail-open guard)"
            )
        params = evaluation.get("parameters", {})
    else:
        params = raw

    condition_tabs = list(params.get("condition_tabs", []))
    raw_cols = params.get("condition_cols")
    condition_cols = (
        [list(inner) for inner in raw_cols] if raw_cols is not None else []
    )
    raw_orders = params.get("ignore_orders")
    ignore_orders = [bool(b) for b in raw_orders] if raw_orders is not None else []

    return EvalSpec(
        condition_tabs=condition_tabs,
        condition_cols=condition_cols,
        ignore_orders=ignore_orders,
    )
