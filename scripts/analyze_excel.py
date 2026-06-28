#!/usr/bin/env python3
"""Analyze Excel files: summary, charts, and Markdown report per sheet."""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.table_analyzer import analyze_dataframe
from scripts.shared import to_json, log


def main():
    parser = argparse.ArgumentParser(description="Excel analysis tool")
    parser.add_argument("path")
    parser.add_argument("--sheet")
    parser.add_argument("--title", default=None)
    parser.add_argument("--out-dir", default="agents/data-analyst/temp")
    parser.add_argument("--max-categories", type=int, default=10)
    args = parser.parse_args()

    try:
        xl = pd.ExcelFile(args.path)
        sheets = xl.sheet_names
        target = args.sheet if args.sheet else sheets[0]
        df = pd.read_excel(args.path, sheet_name=target)
        source_name = f"{Path(args.path).stem}_{target}"
        title = args.title or source_name
        result = analyze_dataframe(df, title, source_name, args.out_dir, args.max_categories)
        print(to_json(result))
    except Exception as e:
        log.error(f"Excel analysis failed: {e}")
        print(to_json({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
