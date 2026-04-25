#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = ROOT / "results" / "analysis"
FIGURES_DIR = ANALYSIS_DIR / "figures"

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.titlesize": 17,
        "axes.labelsize": 14,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "legend.fontsize": 12,
    }
)


MODEL_COLORS = {
    "Claude Sonnet 4": "#4C78A8",
    "OpenAI GPT-4o": "#F58518",
    "OpenAI GPT-4o-mini": "#E45756",
    "Gemini 2.5 Flash": "#72B7B2",
    "Llama 3.2 3B": "#54A24B",
}

MODEL_SHORT_LABELS = {
    "Claude Sonnet 4": "Claude",
    "OpenAI GPT-4o": "GPT-4o",
    "OpenAI GPT-4o-mini": "GPT-4o-mini",
    "Gemini 2.5 Flash": "Gemini",
    "Llama 3.2 3B": "Llama 3.2 3B",
}

AGENT_COLORS = {
    "One-shot (Claude)": "#4C78A8",
    "Generic ReAct": "#E45756",
    "Bounded ReAct": "#F58518",
    "DiagnosticAgent": "#72B7B2",
}

CATEGORY_LABELS = {
    "availability_rollout": "Availability",
    "service_wiring_configuration": "Service wiring",
    "resource_performance": "Resource",
    "dependency_path_trace_centered": "Dependency",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def pct(num: float, den: float) -> float:
    return 100.0 * float(num) / float(den) if den else 0.0


def _style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle="--", linewidth=0.8)
    ax.set_axisbelow(True)


def _side_legend(fig: plt.Figure, handles, labels) -> None:
    fig.legend(
        handles,
        labels,
        frameon=False,
        ncols=1,
        loc="center left",
        bbox_to_anchor=(0.86, 0.5),
        borderaxespad=0.0,
    )


def figure_main_model_comparison(models_json: dict) -> Path:
    rows = []
    for model, payload in models_json["models"].items():
        episodes = payload["episodes"]
        rows.append(
            {
                "Model": MODEL_SHORT_LABELS.get(model, model),
                "Exact": pct(payload["exact"], episodes),
                "Family": pct(payload["family"], episodes),
                "Action": pct(payload["action"], episodes),
            }
        )
    rows.append(
        {
            "Model": "Llama 3.2 3B",
            "Exact": pct(6, 46),
            "Family": pct(6, 46),
            "Action": pct(4, 46),
        }
    )
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(11.2, 7.2))
    x = range(len(df))
    width = 0.24
    bars1 = ax.bar([i - width for i in x], df["Exact"], width, label="Exact", color="#4C78A8")
    bars2 = ax.bar(x, df["Family"], width, label="Family", color="#72B7B2")
    bars3 = ax.bar([i + width for i in x], df["Action"], width, label="Action", color="#F58518")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["Model"], rotation=15, ha="right")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 108)
    ax.set_title("Main Benchmark Results Across Models", pad=34)
    _style_axes(ax)
    handles, labels = ax.get_legend_handles_labels()
    _side_legend(fig, handles, labels)
    fig.subplots_adjust(top=0.88, bottom=0.14, right=0.82)
    out = FIGURES_DIR / "figure_main_model_comparison.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def figure_category_breakdown(category_json: dict) -> Path:
    keep_runs = {
        "Claude one-shot": "Claude",
        "OpenAI GPT-4o one-shot": "GPT-4o",
        "Gemini one-shot": "Gemini",
    }
    rows = []
    for item in category_json["category_breakdown"]:
        run = item["run"]
        if run not in keep_runs:
            continue
        rows.append(
            {
                "Model": keep_runs[run],
                "Category": CATEGORY_LABELS[item["category"]],
                "Exact": pct(item["exact"], item["episodes"]),
            }
        )
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="Category", columns="Model", values="Exact").loc[
        ["Availability", "Service wiring", "Resource", "Dependency"]
    ]

    fig, ax = plt.subplots(figsize=(10.8, 7.2))
    x = range(len(pivot.index))
    width = 0.24
    model_names = list(pivot.columns)
    colors = ["#4C78A8", "#F58518", "#72B7B2"]
    bars = []
    for idx, model in enumerate(model_names):
        offset = (idx - 1) * width
        b = ax.bar([i + offset for i in x], pivot[model], width, label=model, color=colors[idx])
        bars.append(b)
    ax.set_xticks(list(x))
    ax.set_xticklabels(pivot.index)
    ax.set_ylabel("Exact Accuracy (%)")
    ax.set_ylim(0, 108)
    ax.set_title("Exact Accuracy by Fault Category", pad=34)
    _style_axes(ax)
    handles, labels = ax.get_legend_handles_labels()
    _side_legend(fig, handles, labels)
    fig.subplots_adjust(top=0.88, bottom=0.14, right=0.82)
    out = FIGURES_DIR / "figure_category_breakdown.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def figure_runtime_vs_accuracy(models_json: dict) -> Path:
    rows = []
    for model, payload in models_json["models"].items():
        rows.append(
            {
                "Model": model,
                "Exact": pct(payload["exact"], payload["episodes"]),
                "AvgSeconds": payload["avg_seconds"],
            }
        )
    rows.append({"Model": "Llama 3.2 3B", "Exact": pct(6, 46), "AvgSeconds": 48.856})
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(8.8, 6.4))
    for _, row in df.iterrows():
        color = MODEL_COLORS.get(row["Model"], "#4C78A8")
        ax.scatter(row["AvgSeconds"], row["Exact"], s=140, color=color)
        ax.annotate(
            row["Model"],
            (row["AvgSeconds"], row["Exact"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=10,
        )
    ax.set_xlabel("Average Runtime (seconds)")
    ax.set_ylabel("Exact Accuracy (%)")
    ax.set_title("Runtime vs Exact Accuracy", pad=16)
    _style_axes(ax)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = FIGURES_DIR / "figure_runtime_vs_accuracy.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def figure_agent_architectures(react_json: dict, models_json: dict) -> Path:
    one_shot = models_json["models"]["Claude Sonnet 4"]
    rows = [
        {
            "Agent": "One-shot (Claude)",
            "Exact": pct(one_shot["exact"], one_shot["episodes"]),
            "Family": pct(one_shot["family"], one_shot["episodes"]),
            "Action": pct(one_shot["action"], one_shot["episodes"]),
        }
    ]
    for name in ["Generic ReAct", "Bounded ReAct", "DiagnosticAgent"]:
        payload = react_json[name]["summary"]
        rows.append(
            {
                "Agent": name,
                "Exact": pct(payload["exact"], payload["episodes"]),
                "Family": pct(payload["family"], payload["episodes"]),
                "Action": pct(payload["action"], payload["episodes"]),
            }
        )
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(11.4, 7.2))
    x = range(len(df))
    width = 0.24
    bars1 = ax.bar([i - width for i in x], df["Exact"], width, label="Exact", color="#4C78A8")
    bars2 = ax.bar(x, df["Family"], width, label="Family", color="#72B7B2")
    bars3 = ax.bar([i + width for i in x], df["Action"], width, label="Action", color="#F58518")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["Agent"], rotation=15, ha="right")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 108)
    ax.set_title("Claude: One-shot vs Agent Architectures", pad=34)
    _style_axes(ax)
    handles, labels = ax.get_legend_handles_labels()
    _side_legend(fig, handles, labels)
    fig.subplots_adjust(top=0.88, bottom=0.16, right=0.82)
    out = FIGURES_DIR / "figure_agent_architectures.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    models_json = load_json(ANALYSIS_DIR / "results_so_far_native48_filtered_latest.json")
    react_json = load_json(ANALYSIS_DIR / "react_agent_comparison.json")
    dep_json = load_json(ANALYSIS_DIR / "dependency_grouped_results_latest.json")

    outputs = [
        figure_main_model_comparison(models_json),
        figure_category_breakdown(dep_json),
        figure_runtime_vs_accuracy(models_json),
        figure_agent_architectures(react_json, models_json),
    ]
    print(json.dumps({"generated": [str(path) for path in outputs]}, indent=2))


if __name__ == "__main__":
    main()
