from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, write_text

METRIC_ROWS = [
    ("retrieval_hit_rate", "Retrieval Hit Rate"),
    ("mean_token_f1", "Mean Token F1"),
    ("judge_accuracy", "Judge Accuracy"),
    ("mean_judge_score", "Mean Judge Score (1-5)"),
]


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "✅ PASS" if value else "❌ FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    return "—" if value is None else str(value)


def _quality_lines(quality: dict[str, Any]) -> list[str]:
    lines = [
        f"- Gate status: **{_fmt(quality.get('success'))}**",
        f"- Expectations passed: {quality.get('expectations_passed')}/{quality.get('expectations_total')}",
        "",
        "| Expectation | Column | Result | Observed | Unexpected |",
        "|---|---|---|---|---|",
    ]
    for check in quality.get("checks", []):
        lines.append(
            f"| `{check['expectation']}` | {_fmt(check.get('column'))} | {_fmt(check['success'])} "
            f"| {_fmt(check.get('observed_value'))} | {_fmt(check.get('unexpected_count'))} |"
        )
    return lines


def _freshness_lines(freshness: dict[str, Any]) -> list[str]:
    return [
        f"- Latest published: {_fmt(freshness.get('latest_published'))}",
        f"- Oldest published: {_fmt(freshness.get('oldest_published'))}",
        f"- Stale rows (> {freshness.get('threshold_days')} days): "
        f"{freshness.get('stale_rows')}/{freshness.get('total_rows')} ({freshness.get('stale_ratio', 0):.1%})",
        f"- Is fresh (stale ratio ≤ {freshness.get('max_stale_ratio', 0.25):.0%}): **{_fmt(freshness.get('is_fresh'))}**",
    ]


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase."""
    lines = [
        "# Phase 1 Report — Baseline Data Pipeline",
        "",
        f"_Generated at {now_utc().isoformat()}_",
        "",
        "## 1. Source Summary",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in source_summary.items()]
    lines += ["", "## 2. Retrieval & Evaluation Metrics", "", "| Metric | Value |", "|---|---|"]
    lines += [f"| {label} | {_fmt(metrics.get(key))} |" for key, label in METRIC_ROWS]
    lines += [f"| Samples | {_fmt(metrics.get('samples'))} |", ""]
    lines += ["## 3. Data Quality Gate (Great Expectations 1.x)", ""] + _quality_lines(quality)
    lines += ["", "## 4. Freshness", ""] + _freshness_lines(freshness)
    write_text(Path(report_path), "\n".join(lines) + "\n")


def build_comparison_rows(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> list[tuple[str, Any, Any, Any]]:
    return [
        (label, baseline_metrics.get(key), corrupted_metrics.get(key), repaired_metrics.get(key))
        for key, label in METRIC_ROWS
    ]


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    lines = [
        "# Corruption Report — Baseline vs Corrupted vs Repaired",
        "",
        f"_Generated at {now_utc().isoformat()}_",
        "",
        "## 1. Performance Comparison",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |",
        "|---|---|---|---|---|---|",
    ]
    for label, base, corrupted, repaired in build_comparison_rows(baseline_metrics, corrupted_metrics, repaired_metrics):
        delta_c = corrupted - base if isinstance(base, (int, float)) and isinstance(corrupted, (int, float)) else None
        delta_r = repaired - base if isinstance(base, (int, float)) and isinstance(repaired, (int, float)) else None
        lines.append(
            f"| {label} | {_fmt(base)} | {_fmt(corrupted)} | {_fmt(repaired)} "
            f"| {'—' if delta_c is None else f'{delta_c:+.4f}'} | {'—' if delta_r is None else f'{delta_r:+.4f}'} |"
        )

    lines += [
        "",
        "## 2. Quality Gate Status",
        "",
        "| Stage | Gate | Rows | Failed expectations | Fresh |",
        "|---|---|---|---|---|",
    ]
    for stage, quality, freshness in (
        ("Corrupted", corrupted_quality, corrupted_freshness),
        ("Repaired", repaired_quality, repaired_freshness),
    ):
        failed = ", ".join(f"`{name}`" for name in quality.get("failed_expectations", [])) or "—"
        lines.append(
            f"| {stage} | {_fmt(quality.get('success'))} | {quality.get('row_count')} | {failed} | {_fmt(freshness.get('is_fresh'))} |"
        )

    lines += ["", "### Corrupted — expectation details", ""] + _quality_lines(corrupted_quality)
    lines += ["", "### Repaired — expectation details", ""] + _quality_lines(repaired_quality)
    lines += ["", "## 3. Freshness", "", "**Corrupted**", ""] + _freshness_lines(corrupted_freshness)
    lines += ["", "**Repaired**", ""] + _freshness_lines(repaired_freshness)

    base_hit = baseline_metrics.get("retrieval_hit_rate")
    rep_hit = repaired_metrics.get("retrieval_hit_rate")
    recovered = isinstance(base_hit, (int, float)) and isinstance(rep_hit, (int, float)) and rep_hit >= base_hit
    lines += [
        "",
        "## 4. Conclusion",
        "",
        "- Corrupted data was still indexed and answered without runtime errors (**silent failure**); "
        "only the quality gate and metrics reveal the damage.",
        f"- Repair from raw snapshot {'fully restored' if recovered else 'did not fully restore'} baseline retrieval performance.",
    ]
    write_text(Path(report_path), "\n".join(lines) + "\n")
