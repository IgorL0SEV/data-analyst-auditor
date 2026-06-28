#!/usr/bin/env python3
"""NocoDB REST API client for reading tables and records.
This agent is read-only. Only GET operations are supported.
"""
import sys
import json
import argparse
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import NOCODB_BASE_URL, NOCODB_API_TOKEN
from scripts.shared import to_json, log


def headers():
    if not NOCODB_API_TOKEN:
        raise ValueError("NOCODB_API_TOKEN not configured")
    return {
        "xc-token": NOCODB_API_TOKEN,
        "Content-Type": "application/json",
    }


def list_tables(base_id):
    url = f"{NOCODB_BASE_URL}/api/v2/meta/bases/{base_id}/tables"
    resp = requests.get(url, headers=headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_records(base_id, table_id, limit=100, offset=0):
    url = f"{NOCODB_BASE_URL}/api/v1/db/data/noco/{base_id}/{table_id}"
    params = {"limit": limit, "offset": offset}
    resp = requests.get(url, headers=headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="NocoDB read-only client")
    parser.add_argument("command", choices=["tables", "records"])
    parser.add_argument("--base-id")
    parser.add_argument("--table-id")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    if not NOCODB_BASE_URL:
        log.error("NOCODB_BASE_URL not configured")
        print(to_json({"error": "NOCODB_BASE_URL not configured"}))
        sys.exit(1)

    try:
        if args.command == "tables":
            if not args.base_id:
                raise ValueError("Provide --base-id")
            print(to_json(list_tables(args.base_id)))
        elif args.command == "records":
            if not args.base_id or not args.table_id:
                raise ValueError("Provide --base-id and --table-id")
            print(to_json(list_records(args.base_id, args.table_id, args.limit, args.offset)))
    except Exception as e:
        log.error(f"NocoDB request failed: {e}")
        print(to_json({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
