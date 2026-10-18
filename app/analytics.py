"""Local, reproducible DuckDB store for pilot runs and evaluations."""

import json
from pathlib import Path

import duckdb

from app.pricing import estimated_openai_cost


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    database = duckdb.connect(str(path))
    database.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id VARCHAR PRIMARY KEY, document_id VARCHAR, source VARCHAR,
            model VARCHAR, prompt_version VARCHAR, status VARCHAR, error_code VARCHAR,
            input_tokens INTEGER, output_tokens INTEGER, model_elapsed_ms INTEGER,
            estimated_openai_usd DOUBLE
        )
    """)
    database.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            run_id VARCHAR, field VARCHAR, status VARCHAR, value_json VARCHAR,
            evidence_json VARCHAR, issue VARCHAR, PRIMARY KEY (run_id, field)
        )
    """)
    database.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            run_id VARCHAR, field VARCHAR, reference_status VARCHAR,
            prediction_status VARCHAR, tp INTEGER, fp INTEGER, fn INTEGER,
            correct_absent INTEGER, scorable BOOLEAN, evidence_support BOOLEAN,
            evidence_token_f1 DOUBLE, evidence_span_iou DOUBLE,
            PRIMARY KEY (run_id, field)
        )
    """)
    return database


def save_run(database, run_id: str, run: dict, scores: dict[str, dict]) -> None:
    metadata = run["metadata"]
    database.execute("""
        INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [run_id, run["document_id"], metadata["source"], metadata["model"],
          metadata["prompt_version"], run["status"], run.get("error_code"),
          metadata.get("input_tokens"), metadata.get("output_tokens"),
          metadata["elapsed_ms"], estimated_openai_cost(metadata)])
    for field, score in scores.items():
        key = {"Document Name": "document_name", "Parties": "parties",
               "Agreement Date": "agreement_date", "Effective Date": "effective_date",
               "Governing Law": "governing_law"}[field]
        prediction = (run.get("extraction") or {}).get(key) or {}
        database.execute("""
            INSERT OR REPLACE INTO predictions VALUES (?, ?, ?, ?, ?, ?)
        """, [run_id, field, prediction.get("status", "processing_failed"),
              json.dumps(prediction.get("value")), json.dumps(prediction.get("evidence", [])),
              prediction.get("issue")])
        database.execute("""
            INSERT OR REPLACE INTO evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [run_id, field, score["reference_status"], score["prediction_status"],
              score["tp"], score["fp"], score["fn"], score["correct_absent"],
              score["scorable"], score["evidence_support"],
              score["evidence_token_f1"], score["evidence_span_iou"]])
