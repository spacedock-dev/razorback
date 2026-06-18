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
    (HERE / "spider2_eval.jsonl").write_text(
        json.dumps(
            {
                "condition_tabs": ["orders"],
                "condition_cols": {"orders": [0, 1]},
                "ignore_orders": True,
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    build()
