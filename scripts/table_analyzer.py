#!/usr/bin/env python3
"""Shared table analyzer: takes a pandas DataFrame, produces summary, charts, report."""
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from scripts.llm_client import llm_insights
from scripts.shared import log, to_json


def infer_kind(values):
    """Infer whether a pandas Series is numeric, datetime, or categorical."""
    import pandas as pd
    numeric = 0
    dt = 0
    total = 0
    for v in values:
        if pd.isna(v) or v == "" or v is None:
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
    import pandas as pd
    if pd.isna(v) or v == "" or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(" ", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def summarize_dataframe(df):
    import pandas as pd
    if df.empty:
        return {}
    summary = {}
    for col in df.columns:
        values = df[col].tolist()
        kind = infer_kind(values)
        non_null = [v for v in values if not pd.isna(v) and v != ""]
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
    lines = []
    empty_cols = [col for col, s in summary.items() if s["non_null"] == 0]
    if empty_cols:
        lines.append(
            f"- **Пустые колонки:** {', '.join(f'`{c}`' for c in empty_cols)} — "
            "рассмотрите удаление или заполнение."
        )

    for col, s in summary.items():
        if s["non_null"] == 0:
            continue
        if s["kind"] == "numeric":
            min_v = s.get("min")
            max_v = s.get("max")
            mean_v = s.get("mean")
            nulls = s["null_or_empty"]
            note = f"- **{col}**: числовая колонка, диапазон `{min_v}`–`{max_v}`, среднее `{mean_v}`."
            if nulls > 0:
                note += f" Пропусков: {nulls} ({round(100*nulls/row_count,1)}%)."
            lines.append(note)
        elif s["kind"] == "categorical":
            top = s.get("top_values", [])
            if not top:
                continue
            non_null = s["non_null"]
            dominant_val, dominant_cnt = top[0]
            dominant_pct = round(100 * dominant_cnt / non_null, 1)
            unique_ratio = len(top) / non_null if non_null else 0
            lower = col.lower()

            if any(word in lower for word in ["status", "stage", "state", "pipeline"]):
                total = sum(v for _, v in top)
                lost = next((v for k, v in top if k in ("lost", "rejected", "cancelled", "closed_lost")), 0)
                lost_pct = round(100 * lost / total, 1) if total else 0
                if len(top) == 4 and all(v == top[0][1] for _, v in top):
                    lines.append(
                        f"- **{col}**: статусы распределены равномерно ({top[0][1]} каждый). "
                        f"Доля `lost`: {lost_pct}%. Проанализируйте причины отвала и оптимизируйте воронку."
                    )
                else:
                    lines.append(
                        f"- **{col}**: распределение статусов. Лидер: `{dominant_val}` ({dominant_pct}%). "
                        f"Доля `lost`/`rejected`: {lost_pct}%."
                    )
                continue

            if any(word in lower for word in ["source", "channel", "origin", "referrer", "utm"]):
                if len(top) >= 3:
                    leaders = ", ".join(f"`{k}` ({v})" for k, v in top[:3])
                    lines.append(
                        f"- **{col}**: топ-каналы: {leaders}. "
                        f"Сравните CAC и конверсию, перераспределите бюджет."
                    )
                else:
                    lines.append(
                        f"- **{col}**: доминирует `{dominant_val}` ({dominant_pct}%). "
                        f"Диверсифицируйте источники, чтобы снизить зависимость."
                    )
                continue

            if "campaign" in lower:
                lines.append(
                    f"- **{col}**: кампании распределены. Лидер: `{dominant_val}` ({dominant_cnt} записей). "
                    f"Сравните CPA/LTV по кампаниям."
                )
                continue

            if any(word in lower for word in ["manager", "owner", "assignee", "responsible"]):
                lines.append(
                    f"- **{col}**: нагрузка на {len(top)} менеджеров/владельцев. "
                    f"Лидер: `{dominant_val}` ({dominant_cnt} записей)."
                )
                continue

            if any(word in lower for word in ["country", "city", "region", "location"]):
                if len(top) <= 3:
                    lines.append(
                        f"- **{col}**: география сконцентрирована в {len(top)} локациях. "
                        f"Лидер: `{dominant_val}` ({dominant_pct}%). Рассмотрите региональные кампании."
                    )
                else:
                    leaders = ", ".join(f"`{k}` ({v})" for k, v in top[:3])
                    lines.append(
                        f"- **{col}**: широкая география. Топ-локации: {leaders}."
                    )
                continue

            if any(word in lower for word in ["product", "item", "sku", "service"]):
                lines.append(
                    f"- **{col}**: топ-товар/услуга: `{dominant_val}` ({dominant_cnt} записей). "
                    f"Проанализируйте спрос и возможности кросс-селла."
                )
                continue

            if unique_ratio > 0.8:
                lines.append(
                    f"- **{col}**: преимущественно уникальные значения ({len(top)} distinct). "
                    f"Не подходит для агрегации; скорее всего идентификатор или имя."
                )
            elif dominant_pct >= 50:
                lines.append(
                    f"- **{col}**: сильный перекос к `{dominant_val}` ({dominant_pct}%). "
                    f"Исследуйте, почему другие значения недопредставлены."
                )
            elif dominant_pct >= 25:
                lines.append(
                    f"- **{col}**: лидер `{dominant_val}` ({dominant_pct}%). "
                    f"Распределение умеренное, полезно сегментировать по этому полю."
                )
            else:
                lines.append(
                    f"- **{col}**: сбалансировано по {len(top)} значениям. "
                    f"Ярко выраженного лидера нет."
                )

    missing_cols = [c for c, s in summary.items() if s["null_or_empty"] > 0]
    if missing_cols:
        total_missing = sum(summary[c]["null_or_empty"] for c in missing_cols)
        lines.append(
            f"- **Качество данных:** {len(missing_cols)} колонок содержат пропуски "
            f"({total_missing} ячеек из {row_count * len(summary)})."
        )
    else:
        lines.append("- **Качество данных:** все колонки заполнены.")

    if not lines:
        lines.append("- Ярких паттернов в данных не выявлено.")
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


def generate_report(title, rows_count, summary, insights_text, charts, out_report):
    lines = [
        f"# Analysis of `{title}`",
        "",
        f"- **Total rows:** {rows_count}",
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


def analyze_dataframe(df, title, source_name, out_dir, max_categories=10):
    import pandas as pd
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize_dataframe(df)
    row_count = len(df)
    safe_title = title or source_name

    summary_payload = to_json({
        "source": source_name,
        "title": title,
        "row_count": row_count,
        "columns": summary,
    })

    summary_path = out_dir / f"{source_name}_summary.json"
    summary_path.write_text(summary_payload, encoding="utf-8")

    insights = llm_insights(summary_payload, row_count, safe_title)
    if insights is None:
        insights = "\n".join(generate_insights(summary, row_count))

    charts = []
    for col, s in summary.items():
        if not should_chart(col, s, row_count):
            continue
        top = s.get("top_values", [])[:max_categories]
        data = build_chart_data(top)
        kind = "bar" if len(data) <= 6 else "pie"
        chart_path = out_dir / f"{source_name}_{col}.png"
        try:
            run_chart(kind, data, f"Distribution by {col}", f"{row_count} rows", chart_path)
            charts.append(str(chart_path))
        except Exception as e:
            log.warning(f"Chart failed for {col}: {e}")

    report_path = out_dir / f"{source_name}_report.md"
    generate_report(safe_title, row_count, summary, insights, charts, report_path)

    return {
        "title": safe_title,
        "row_count": row_count,
        "summary_json": str(summary_path),
        "report_md": str(report_path),
        "charts": charts,
    }
