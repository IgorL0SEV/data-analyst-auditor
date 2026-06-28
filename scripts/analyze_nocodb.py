#!/usr/bin/env python3
"""Read a NocoDB table, build summary stats, charts, and a Markdown report."""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import NOCODB_BASE_URL, NOCODB_API_TOKEN
from scripts.llm_client import llm_insights
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


def infer_kind(values):
    """Infer whether a column is numeric, datetime, or categorical."""
    numeric = 0
    dt = 0
    total = 0
    for v in values:
        if v is None or v == "":
            continue
        total += 1
        if isinstance(v, (int, float)):
            numeric += 1
            continue
        s = str(v)
        try:
            float(s.replace(" ", "").replace(",", ""))
            numeric += 1
            continue
        except ValueError:
            pass
        if "T" in s and ":" in s:
            try:
                datetime.fromisoformat(s.replace("Z", "+00:00"))
                dt += 1
                continue
            except ValueError:
                pass
    if total == 0:
        return "empty"
    if numeric / total >= 0.8:
        return "numeric"
    if dt / total >= 0.8:
        return "datetime"
    return "categorical"


def to_number(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(" ", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def summarize(rows):
    if not rows:
        return {}
    columns = list(rows[0].keys())
    summary = {}
    for col in columns:
        values = [row.get(col) for row in rows]
        kind = infer_kind(values)
        non_null = [v for v in values if v is not None and v != ""]
        col_summary = {
            "total_rows": len(values),
            "non_null": len(non_null),
            "null_or_empty": len(values) - len(non_null),
            "kind": kind,
            "sample_values": non_null[:5],
        }
        if kind == "numeric":
            nums = [to_number(v) for v in values]
            nums = [n for n in nums if n is not None]
            if nums:
                col_summary.update({
                    "min": min(nums),
                    "max": max(nums),
                    "mean": round(sum(nums) / len(nums), 2),
                    "sum": round(sum(nums), 2),
                })
        elif kind == "categorical":
            counts = Counter(str(v) for v in non_null)
            col_summary["top_values"] = counts.most_common(10)
        summary[col] = col_summary
    return summary


def should_chart(col, s, row_count):
    """Skip IDs, unique values, empty columns, and high-cardinality text."""
    if s["kind"] != "categorical":
        return False
    if s["non_null"] == 0:
        return False
    top = s.get("top_values", [])
    if not top:
        return False
    if len(top) == s["non_null"]:
        return False
    if col.lower() in ("id", "id1", "external_lead_id", "email", "phone"):
        return False
    if re.match(r"^.*_id$", col.lower()):
        return False
    lower = col.lower()
    if lower in ("createdat", "updatedat", "created_at", "updated_at", "created_on", "updated_on"):
        return False
    if re.match(r"^.*_(created|updated)_(at|on|date|time)$", lower):
        return False
    if lower.endswith("_at") or lower.endswith("_on") or lower.endswith("_date") or lower.endswith("_time"):
        return False
    if len(top) > max(10, row_count * 0.3):
        return False
    return True


def generate_insights(summary, row_count):
    """Generate human-readable insights and recommendations."""
    lines = []
    empty_cols = [col for col, s in summary.items() if s["non_null"] == 0]
    if empty_cols:
        lines.append(
            f"- **Empty columns:** {', '.join(f'`{c}`' for c in empty_cols)} — "
            "consider removing or populating them."
        )

    numeric_cols = [(c, s) for c, s in summary.items() if s["kind"] == "numeric"]
    for col, s in numeric_cols:
        min_v = s.get("min")
        max_v = s.get("max")
        mean_v = s.get("mean")
        nulls = s["null_or_empty"]
        note = f"- **{col}**: numeric, range `{min_v}`–`{max_v}`, average `{mean_v}`."
        if nulls > 0:
            note += f" Has {nulls} missing values ({round(100*nulls/row_count,1)}%)."
        lines.append(note)

    categorical_cols = [(c, s) for c, s in summary.items() if s["kind"] == "categorical"]
    for col, s in categorical_cols:
        top = s.get("top_values", [])
        if not top:
            continue
        non_null = s["non_null"]
        dominant_val, dominant_cnt = top[0]
        dominant_pct = round(100 * dominant_cnt / non_null, 1)
        unique_ratio = len(top) / non_null if non_null else 0

        lower = col.lower()

        # Status / stage funnel interpretation
        if any(word in lower for word in ["status", "stage", "state", "pipeline"]):
            total = sum(v for _, v in top)
            lost = next((v for k, v in top if k in ("lost", "rejected", "cancelled", "closed_lost")), 0)
            won = next((v for k, v in top if k in ("won", "qualified", "closed_won", "converted")), 0)
            lost_pct = round(100 * lost / total, 1) if total else 0
            won_pct = round(100 * won / total, 1) if total else 0
            if len(top) == 4 and all(v == top[0][1] for _, v in top):
                lines.append(
                    f"- **{col}**: statuses are evenly split ({top[0][1]} each). "
                    f"`lost` share is {lost_pct}%. Analyze why leads drop off and optimize conversion."
                )
            else:
                lines.append(
                    f"- **{col}**: pipeline/status distribution. "
                    f"Most common: `{dominant_val}` ({dominant_pct}%). "
                    f"`lost`/`rejected` share: {lost_pct}%, `won`/`qualified` share: {won_pct}%."
                )
            continue

        # Timestamps that are all equal
        if lower in ("createdat", "created_at", "created_on") and len(top) == 1:
            lines.append(
                f"- **{col}**: all records share the same timestamp (`{top[0][0]}`). "
                f"Likely an import/bulk load date, not the actual creation time."
            )
            continue

        # Source / channel interpretation
        if any(word in lower for word in ["source", "channel", "origin", "referrer", "utm"]):
            if len(top) >= 3:
                leaders = ", ".join(f"`{k}` ({v})" for k, v in top[:3])
                lines.append(
                    f"- **{col}**: top channels are {leaders}. "
                    f"Focus budget on the leaders; test underperforming channels."
                )
            else:
                lines.append(
                    f"- **{col}**: dominated by `{dominant_val}` ({dominant_pct}%). "
                    f"Diversify sources to reduce dependency."
                )
            continue

        # Campaign interpretation
        if "campaign" in lower:
            lines.append(
                f"- **{col}**: campaigns are fairly distributed. "
                f"Top: `{dominant_val}` ({dominant_cnt} records). "
                f"Compare CPA/LTV per campaign for efficiency."
            )
            continue

        # Manager / owner interpretation
        if any(word in lower for word in ["manager", "owner", "assignee", "responsible"]):
            lines.append(
                f"- **{col}**: workload distributed across {len(top)} managers/owners. "
                f"Top owner: `{dominant_val}` ({dominant_cnt} records)."
            )
            continue

        # Country / city / region interpretation
        if any(word in lower for word in ["country", "city", "region", "location"]):
            if len(top) <= 3:
                lines.append(
                    f"- **{col}**: geography is concentrated in {len(top)} locations. "
                    f"Leader: `{dominant_val}` ({dominant_pct}%). Consider regional campaigns."
                )
            else:
                leaders = ", ".join(f"`{k}` ({v})" for k, v in top[:3])
                lines.append(
                    f"- **{col}**: wide geographic spread. Top locations: {leaders}."
                )
            continue

        # Product interpretation
        if any(word in lower for word in ["product", "item", "sku", "service"]):
            lines.append(
                f"- **{col}**: top product/service: `{dominant_val}` ({dominant_cnt} records). "
                f"Analyze stock/demand and cross-sell potential."
            )
            continue

        # Generic categorical interpretation
        if unique_ratio > 0.8:
            lines.append(
                f"- **{col}**: mostly unique values ({len(top)} distinct). "
                f"Not useful for aggregation; likely an identifier or name."
            )
        elif dominant_pct >= 50:
            lines.append(
                f"- **{col}**: heavily skewed toward `{dominant_val}` ({dominant_pct}%). "
                f"Investigate why other values are underrepresented."
            )
        elif dominant_pct >= 25:
            lines.append(
                f"- **{col}**: `{dominant_val}` is the largest group ({dominant_pct}%). "
                f"Distribution is moderate; worth segmenting by this field."
            )
        else:
            lines.append(
                f"- **{col}**: fairly balanced across {len(top)} values. "
                f"No single dominant category."
            )

    if not lines:
        lines.append("- No strong patterns detected in the available data.")

    # Add overall data-quality note
    missing_cols = [c for c, s in summary.items() if s["null_or_empty"] > 0]
    if missing_cols:
        total_missing = sum(summary[c]["null_or_empty"] for c in missing_cols)
        lines.append(
            f"- **Data quality:** {len(missing_cols)} columns have missing values "
            f"({total_missing} cells out of {row_count * len(summary)})."
        )
    else:
        lines.append("- **Data quality:** all columns are fully populated.")

    return lines


def build_chart_data(top_values):
    return [{"label": label, "value": value} for label, value in top_values]


def run_chart(kind, data, title, subtitle, out_path):
    if not data:
        return None
    chart_script = Path(__file__).resolve().parent / "make_chart.py"
    cmd = [
        "python", str(chart_script),
        kind,
        "--data", json.dumps(data, ensure_ascii=False),
        "--title", title,
        "--subtitle", subtitle,
        "--out", str(out_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return str(out_path)


def generate_report(base_id, table_id, table_title, rows, summary, insights_text, charts, out_report):
    lines = [
        f"# Analysis of `{table_title}`",
        "",
        f"- **Base (base_id):** `{base_id}`",
        f"- **Table (table_id):** `{table_id}`",
        f"- **Total rows:** {len(rows)}",
        f"- **Analysis date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Key insights & recommendations",
        "",
    ]
    lines.extend(insights_text.splitlines())
    lines.extend([
        "",
        "## Column summary",
        "",
        "| Column | Type | Filled | Empty/NULL | Min | Max | Mean | Sum | Top values |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for col, s in summary.items():
        kind = s["kind"]
        filled = s["non_null"]
        empty = s["null_or_empty"]
        min_v = s.get("min", "—")
        max_v = s.get("max", "—")
        mean_v = s.get("mean", "—")
        sum_v = s.get("sum", "—")
        if kind == "categorical":
            top = s.get("top_values", [])
            top_str = ", ".join(f"{k} ({v})" for k, v in top[:5])
        else:
            top_str = "—"
        lines.append(f"| {col} | {kind} | {filled} | {empty} | {min_v} | {max_v} | {mean_v} | {sum_v} | {top_str} |")

    if charts:
        lines.extend(["", "## Charts", ""])
        for chart in charts:
            rel = Path(chart).name
            lines.append(f"### {Path(chart).stem}")
            lines.append(f"![{rel}]({rel})")
            lines.append("")

    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines), encoding="utf-8")
    return str(out_report)


def analyze(base_id, table_id, table_title=None, out_dir=None, max_categories=10):
    out_dir = Path(out_dir or "agents/data-analyst/temp")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = table_title or table_id

    rows = fetch_records(base_id, table_id)
    summary = summarize(rows)

    summary_payload = to_json({
        "base_id": base_id,
        "table_id": table_id,
        "table_title": table_title,
        "row_count": len(rows),
        "columns": summary,
    })

    summary_path = out_dir / f"nocodb_{base_id}_{table_id}_summary.json"
    summary_path.write_text(summary_payload, encoding="utf-8")

    # Try LLM insights first, then fall back to rule-based
    insights = llm_insights(summary_payload, len(rows), safe_title)
    if insights is None:
        insights = "\n".join(generate_insights(summary, len(rows)))

    charts = []
    for col, s in summary.items():
        if not should_chart(col, s, len(rows)):
            continue
        top = s.get("top_values", [])[:max_categories]
        data = build_chart_data(top)
        kind = "bar" if len(data) <= 6 else "pie"
        chart_path = out_dir / f"nocodb_{base_id}_{table_id}_{col}.png"
        try:
            run_chart(kind, data, f"Distribution by {col}", f"{len(rows)} rows", chart_path)
            charts.append(str(chart_path))
        except Exception as e:
            log.warning(f"Chart failed for {col}: {e}")

    report_path = out_dir / f"nocodb_{base_id}_{table_id}_report.md"
    generate_report(base_id, table_id, safe_title, rows, summary, insights, charts, report_path)

    return {
        "base_id": base_id,
        "table_id": table_id,
        "table_title": table_title,
        "row_count": len(rows),
        "summary_json": str(summary_path),
        "report_md": str(report_path),
        "charts": charts,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze a NocoDB table and generate report + charts")
    parser.add_argument("--base-id", required=True)
    parser.add_argument("--table-id", required=True)
    parser.add_argument("--table-title", default=None)
    parser.add_argument("--out-dir", default="agents/data-analyst/temp")
    parser.add_argument("--max-categories", type=int, default=10)
    args = parser.parse_args()

    try:
        result = analyze(args.base_id, args.table_id, args.table_title, args.out_dir, args.max_categories)
        print(to_json(result))
    except Exception as e:
        log.error(f"NocoDB analysis failed: {e}")
        print(to_json({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
