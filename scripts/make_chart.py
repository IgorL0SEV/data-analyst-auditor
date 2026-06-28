#!/usr/bin/env python3
"""Chart generator using matplotlib (no clipping, handles Russian text)."""
import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.shared import log

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.grid": True,
    "grid.color": "#e5e7eb",
    "grid.linewidth": 0.8,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

COLORS = ["#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#1d4ed8",
          "#16a34a", "#f97316", "#dc2626", "#7c3aed", "#0891b2"]


def auto_fmt(values, unit=""):
    max_v = max(abs(v) for v in values) if values else 1
    suffix = f" {unit}" if unit else ""
    if max_v >= 1_000_000_000:
        return lambda v: f"{v/1e9:.2f} млрд{suffix}"
    if max_v >= 1_000_000:
        return lambda v: f"{v/1e6:.1f} млн{suffix}"
    if max_v >= 10_000:
        return lambda v: f"{v:,.0f}{suffix}"
    return lambda v: f"{v:.2f}{suffix}"


def make_bar(data, title, subtitle, out, unit=""):
    labels = [d["label"] for d in data]
    values = [d["value"] for d in data]
    fmt = auto_fmt(values, unit)
    max_v = max(values) if values else 1

    n = len(labels)
    fig, ax = plt.subplots(figsize=(12, max(4, 0.6 * n + 2.5)))
    colors = [COLORS[i % len(COLORS)] for i in range(n)]
    bars = ax.barh(labels, values, color=colors, height=0.55, edgecolor="none")
    ax.invert_yaxis()
    ax.tick_params(axis="y", labelsize=12, colors="#111827")
    ax.tick_params(axis="x", labelsize=10, colors="#6b7280")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{v/1e9:.1f}" if max_v >= 1e9 else
                     f"{v/1e6:.0f}" if max_v >= 1e6 else f"{v:,.0f}"
    ))
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.grid(axis="x")
    ax.set_axisbelow(True)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_v * 0.01,
            bar.get_y() + bar.get_height() / 2,
            fmt(val),
            va="center", ha="left", fontsize=10, color="#374151"
        )
    ax.set_xlim(0, max_v * 1.35)

    fig.suptitle(title, fontsize=18, fontweight="bold", color="#111827", x=0.05, ha="left", y=1.02)
    if subtitle:
        ax.set_title(subtitle, fontsize=10, color="#6b7280", loc="left", pad=6)

    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def make_line(data, title, subtitle, out, unit=""):
    labels = [d["label"] for d in data]
    values = [d["value"] for d in data]
    fmt = auto_fmt(values, unit)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(labels, values, color="#2563eb", linewidth=2.5, marker="o",
            markersize=6, markerfacecolor="white", markeredgewidth=2)
    ax.fill_between(range(len(labels)), values, alpha=0.08, color="#2563eb")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30 if len(labels) > 8 else 0,
                       ha="right" if len(labels) > 8 else "center", fontsize=11)
    ax.tick_params(axis="y", labelsize=10, colors="#6b7280")
    max_v = max(values) if values else 1
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{v/1e9:.1f}" if max_v >= 1e9 else
                     f"{v/1e6:.0f} млн" if max_v >= 1e6 else f"{v:,.0f}"
    ))
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.grid(axis="y")
    ax.set_axisbelow(True)

    for i, val in enumerate(values):
        ax.annotate(fmt(val), (i, val), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9, color="#374151")

    fig.suptitle(title, fontsize=18, fontweight="bold", color="#111827", x=0.05, ha="left", y=1.02)
    if subtitle:
        ax.set_title(subtitle, fontsize=10, color="#6b7280", loc="left", pad=6)

    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def make_pie(data, title, subtitle, out, unit=""):
    labels = [d["label"] for d in data]
    values = [d["value"] for d in data]
    fmt = auto_fmt(values, unit)
    colors = [COLORS[i % len(COLORS)] for i in range(len(values))]

    fig, ax = plt.subplots(figsize=(10, 7))
    wedges, _, autotexts = ax.pie(
        values, colors=colors, autopct=lambda p: f"{p:.1f}%",
        pctdistance=0.75, startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_color("white")
        at.set_fontweight("bold")

    ax.legend(
        wedges, [f"{l} — {fmt(v)}" for l, v in zip(labels, values)],
        loc="lower center", bbox_to_anchor=(0.5, -0.15),
        fontsize=10, frameon=False, ncol=2
    )

    fig.suptitle(title, fontsize=18, fontweight="bold", color="#111827", x=0.05, ha="left", y=1.01)
    if subtitle:
        ax.set_title(subtitle, fontsize=10, color="#6b7280")

    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=["bar", "line", "pie"])
    p.add_argument("--data", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--subtitle", default="")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    try:
        data = json.loads(a.data)
    except json.JSONDecodeError as e:
        log.error(f"Invalid JSON: {e}")
        sys.exit(1)

    os.makedirs(os.path.dirname(a.out) if os.path.dirname(a.out) else ".", exist_ok=True)

    if a.kind == "bar":
        path = make_bar(data, a.title, a.subtitle, a.out)
    elif a.kind == "line":
        path = make_line(data, a.title, a.subtitle, a.out)
    elif a.kind == "pie":
        path = make_pie(data, a.title, a.subtitle, a.out)

    print(json.dumps({"chart": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
