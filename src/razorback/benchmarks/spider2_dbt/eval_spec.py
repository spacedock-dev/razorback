# ABOUTME: spider2-dbt gold eval-spec model + loader (one line of spider2_eval.jsonl).
# ABOUTME: Mirrors Spider2 evaluate.py: evaluation.parameters drives duckdb_match.
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Conservative allowlist for the spec-supplied gold DB basename. A real Spider2
# gold filename is a plain `<word>.duckdb`; restricting to this set blocks path
# traversal AND shell injection at the trust boundary (see load_eval_spec).
_SAFE_GOLD_RE = re.compile(r"[A-Za-z0-9._-]+\.duckdb")


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

    gold: basename of the gold ``.duckdb`` to score against, taken verbatim
        from ``evaluation.parameters.gold``. Real Spider2 tasks name the gold
        DB per task (e.g. ``playbook.duckdb``, ``tpch.duckdb``), so this drives
        which file the verifier compares — it is NOT hardcoded to
        ``gold.duckdb``. Mirrors Spider2 ``evaluate.py:97``, which resolves
        ``parameters['gold']`` to a per-task gold path before calling
        ``duckdb_match``. ``None`` only for bare-``parameters`` fixtures with no
        ``evaluation`` wrapper.
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
    gold: str | None = None

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
    file, a wrong ``evaluation.func``, a missing/empty ``condition_tabs``, or
    (for a real wrapped spec) a missing/empty ``parameters.gold`` each raise
    ``ValueError`` rather than yielding a spec that ``compare_duckdb`` would
    silently score as a match or that would score against the wrong gold file.
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
    wrapped = evaluation is not None
    if wrapped:
        func = evaluation.get("func")
        if func != "duckdb_match":
            raise ValueError(
                f"unsupported evaluation.func {func!r} in {path}: this verifier "
                "only scores 'duckdb_match' (fail-open guard)"
            )
        params = evaluation.get("parameters", {})
    else:
        params = raw

    gold = params.get("gold")
    # A real wrapped Spider2 gold line MUST name its per-task gold DB (Spider2
    # evaluate.py resolves parameters['gold'] to a per-task path). A missing or
    # empty gold basename means we cannot know which file to score against, so
    # fail closed rather than fall back to a hardcoded gold.duckdb.
    if wrapped and not (isinstance(gold, str) and gold.strip()):
        raise ValueError(
            f"missing/empty evaluation.parameters.gold in {path}: a wrapped "
            "duckdb_match spec must name its per-task gold .duckdb (fail-open "
            "guard)"
        )
    # `gold` is external Spider2 input that the materializer joins onto a path
    # (tests/gold/<gold>) and emits UNQUOTED into the verifier test.sh
    # (--gold-db /tests/<gold>). A conservative allowlist closes the whole class
    # at the trust boundary: it subsumes the path checks (no separators, `..`, or
    # absolute paths get through) AND rejects shell metacharacters/whitespace, so
    # a malformed/hostile spec can neither escape tests/gold/ nor inject shell
    # syntax into the verifier script. Real Spider2 gold names are plain
    # `<word>.duckdb`, so this is tighter than the data requires by design.
    if isinstance(gold, str) and gold.strip():
        g = gold.strip()
        if not _SAFE_GOLD_RE.fullmatch(g):
            raise ValueError(
                f"unsafe evaluation.parameters.gold {gold!r} in {path}: must "
                "match [A-Za-z0-9._-]+.duckdb (a bare .duckdb basename, no path "
                "separators, '..', whitespace, or shell metacharacters) — "
                "refusing to score outside tests/gold/ or inject into test.sh "
                "(fail-closed)"
            )
        gold = g

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
        gold=gold if isinstance(gold, str) else None,
    )
