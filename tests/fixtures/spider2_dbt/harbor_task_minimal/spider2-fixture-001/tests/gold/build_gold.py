# ABOUTME: Rebuilds the gold .duckdb for the spider2-dbt verifier fixture.
# ABOUTME: Run: uv run python <this file>  (regenerates gold.duckdb next to it).
import json
from pathlib import Path

import duckdb

HERE = Path(__file__).parent


def build() -> None:
    db = HERE / "gold.duckdb"
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    try:
        con.execute("CREATE TABLE orders (id INTEGER, amount INTEGER)")
        con.executemany("INSERT INTO orders VALUES (?, ?)", [(1, 100), (2, 200)])
    finally:
        con.close()
    # Real Spider2 gold-line shape (spider2-dbt/evaluation_suite/evaluate.py):
    # instance_id + evaluation.parameters with per-table List[List[int]]
    # condition_cols and List[bool] ignore_orders.
    (HERE / "spider2_eval.jsonl").write_text(
        json.dumps(
            {
                "instance_id": "spider2-fixture-001",
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {
                        "gold": "gold.duckdb",
                        "condition_tabs": ["orders"],
                        "condition_cols": [[0, 1]],
                        "ignore_orders": [True],
                    },
                },
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    build()
