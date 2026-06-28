#!/usr/bin/env python3
"""Analyze CSV files: summary, charts, and Markdown report."""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.table_analyzer import analyze_dataframe
from scripts.shared import to_json, log


def main():
    parser = argparse.ArgumentParser(description="CSV analysis tool")
    parser.add_argument("path")
    parser.add_argument("--title", default=None)
    parser.add_argument("--out-dir", default="agents/data-analyst/temp")
    parser.add_argument("--max-categories", type=int, default=10)
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.path)
        source_name = Path(args.path).stem
        title = args.title or source_name
        result = analyze_dataframe(df, title, source_name, args.out_dir, args.max_categories)
        print(to_json(result))
    except Exception as e:
        log.error(f"CSV analysis failed: {e}")
        print(to_json({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
