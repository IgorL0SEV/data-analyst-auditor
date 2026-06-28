#!/usr/bin/env python3
"""Execute SQL queries against any SQLAlchemy-supported database.
By default only SELECT and read-only CTEs are allowed.
Write queries require --write flag and explicit confirmation from user.
"""
import sys
import re
import argparse
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DATABASE_URL
from scripts.shared import to_json, log

WRITE_KEYWORDS = {"insert", "update", "delete", "drop", "create", "alter", "truncate", "grant", "revoke"}


def is_read_only(sql):
    """Check if SQL is read-only (SELECT or WITH ... SELECT without write keywords)."""
    cleaned = re.sub(r"--.*", " ", sql)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    tokens = re.findall(r"\b\w+\b", cleaned.lower())
    if not tokens:
        return False
    if tokens[0] not in {"select", "with"}:
        return False
    return not any(kw in tokens for kw in WRITE_KEYWORDS)


def query(db_url, sql, limit=500):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        if result.returns_rows:
            cols = list(result.keys())
            rows = result.mappings().fetchmany(limit)
            rows = [dict(row) for row in rows]
            return {"columns": cols, "rows": rows, "count": len(rows)}
        else:
            conn.commit()
            return {"affected": result.rowcount}


def main():
    parser = argparse.ArgumentParser(description="Database SQL query tool")
    parser.add_argument("sql")
    parser.add_argument("--db-url", default=DATABASE_URL)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true",
                        help="Allow INSERT/UPDATE/DELETE/DDL queries. Requires explicit user confirmation.")
    args = parser.parse_args()

    if not args.db_url:
        log.error("Database URL not configured. Set DATABASE_URL in .env")
        print(to_json({"error": "Database URL not configured"}))
        sys.exit(1)

    if not is_read_only(args.sql) and not args.write:
        log.error("Write/DDL query blocked. Use --write only after explicit user confirmation.")
        print(to_json({
            "error": "Write/DDL query blocked. Use --write only after explicit user confirmation.",
            "hint": "This agent is read-only by default to protect source databases."
        }))
        sys.exit(1)

    try:
        result = query(args.db_url, args.sql, args.limit)
        if args.json:
            print(to_json(result))
        else:
            rows = result.get("rows", [])
            if not rows:
                print(to_json(result))
            else:
                cols = result["columns"]
                lines = [" | ".join(str(c) for c in cols)]
                lines.append("-" * len(lines[0]))
                for row in rows[:50]:
                    lines.append(" | ".join(str(row.get(c, "")) for c in cols))
                if len(rows) > 50:
                    lines.append(f"... и ещё {len(rows) - 50} строк")
                lines.append(f"\nВсего строк: {result['count']}")
                print("\n".join(lines))
    except Exception as e:
        log.error(f"DB query failed: {e}")
        print(to_json({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
