#!/usr/bin/env python3
"""Read a NocoDB table and analyze it via shared table_analyzer."""
import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import NOCODB_BASE_URL, NOCODB_API_TOKEN
from scripts.table_analyzer import analyze_dataframe
from scripts.shared import log, to_json


def fetch_records(base_id, table_id, limit=1000):
    url = f"{NOCODB_BASE_URL}/api/v1/db/data/noco/{base_id}/{table_id}"
    headers = {"xc-token": NOCODB_API_TOKEN}
    all_rows = []
    offset = 0
    while True:
        params = {"limit": limit, "offset": offset}
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("list", [])
        if not rows:
            break
        all_rows.extend(rows)
        offset += len(rows)
        page_info = data.get("pageInfo", {})
        if page_info.get("isLastPage"):
            break
    return all_rows


def main():
    parser = argparse.ArgumentParser(description="Analyze a NocoDB table and generate report + charts")
    parser.add_argument("--base-id", required=True)
    parser.add_argument("--table-id", required=True)
    parser.add_argument("--table-title", default=None)
    parser.add_argument("--out-dir", default="agents/data-analyst/temp")
    parser.add_argument("--max-categories", type=int, default=10)
    args = parser.parse_args()

    if not NOCODB_BASE_URL or not NOCODB_API_TOKEN:
        log.error("NOCODB_BASE_URL and NOCODB_API_TOKEN must be configured")
        print(to_json({"error": "NocoDB not configured"}))
        sys.exit(1)

    try:
        rows = fetch_records(args.base_id, args.table_id)
        df = pd.DataFrame(rows)
        source_name = f"nocodb_{args.base_id}_{args.table_id}"
        title = args.table_title or source_name
        result = analyze_dataframe(df, title, source_name, args.out_dir, args.max_categories)
        result["base_id"] = args.base_id
        result["table_id"] = args.table_id
        print(to_json(result))
    except Exception as e:
        log.error(f"NocoDB analysis failed: {e}")
        print(to_json({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
