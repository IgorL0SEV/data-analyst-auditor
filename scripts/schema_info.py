#!/usr/bin/env python3
"""Print relational DB schema info (read-only) via SQLAlchemy."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DATABASE_URL
from scripts.shared import log, to_json


def get_schema_info(db_url):
    try:
        import sqlalchemy
    except ImportError as e:
        raise RuntimeError("sqlalchemy is required for schema_info") from e

    engine = sqlalchemy.create_engine(db_url)
    inspector = sqlalchemy.inspect(engine)
    schema = {}
    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)
        pk = inspector.get_pk_constraint(table).get("constrained_columns", [])
        try:
            with engine.connect() as conn:
                count = conn.execute(sqlalchemy.text(f"SELECT count(*) FROM {table}")).scalar()
        except Exception as e:
            log.warning(f"Could not count rows in {table}: {e}")
            count = None
        schema[table] = {
            "row_count": count,
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable"),
                    "default": str(col.get("default")) if col.get("default") else None,
                    "primary_key": col["name"] in pk,
                }
                for col in columns
            ],
        }
    return schema


def main():
    parser = argparse.ArgumentParser(description="Print DB schema info")
    parser.add_argument("--db-url", default=DATABASE_URL)
    args = parser.parse_args()

    if not args.db_url:
        print(to_json({"error": "DATABASE_URL not configured"}))
        sys.exit(1)

    try:
        schema = get_schema_info(args.db_url)
        print(to_json(schema))
    except Exception as e:
        log.error(f"Schema info failed: {e}")
        print(to_json({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
