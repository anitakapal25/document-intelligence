"""Confirm the local Phoenix collector persisted the connection-check span."""

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    database = ROOT / "outputs/phoenix/phoenix.db"
    if not database.exists():
        raise SystemExit("Phoenix database was not found")
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE '%span%'"
        )]
        print(f"Span tables: {tables}")
        for table in tables:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            if "name" in columns:
                count = connection.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE name = ?',
                    ("phoenix_connection_check",),
                ).fetchone()[0]
                if count:
                    print(f"Persisted connection-check spans: {count}")
                    return
    finally:
        connection.close()
    raise SystemExit("Connection-check span was not found")


if __name__ == "__main__":
    main()
