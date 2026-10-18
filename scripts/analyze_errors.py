"""Print development disagreements without exposing full contract text."""

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    database = duckdb.connect(str(ROOT / "data/processed/benchmark.duckdb"), read_only=True)
    rows = database.execute("""
        SELECT e.field, r.document_id, e.reference_status, e.prediction_status,
               e.tp, e.fp, e.fn, p.value_json, p.issue
        FROM evaluations e
        JOIN runs r USING (run_id)
        JOIN predictions p USING (run_id, field)
        WHERE r.source = 'cuad_supplied_text'
          AND (e.fp > 0 OR e.fn > 0 OR e.prediction_status = 'failed')
        ORDER BY e.field, r.document_id
    """).fetchall()
    for field, title, reference, prediction, tp, fp, fn, value, issue in rows:
        print(f"{field}: {title[:64]} | ref={reference}, pred={prediction}, "
              f"tp/fp/fn={tp}/{fp}/{fn}, value={value}, issue={issue}")
    database.close()


if __name__ == "__main__":
    main()
